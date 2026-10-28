"""Indicador de estado del daemon en la bandeja del sistema (Ola 24).

Escucha al daemon como un cliente más y muestra un círculo: verde si el navegador está
conectado (la llamada o la presentación), amarillo si el daemon responde pero el navegador
no, gris si no hay daemon. Cada cambio queda en el registro (`cast.log`).

La bandeja usa `pystray` (extra opcional `bandeja`). En GNOME hace falta la extensión
«AppIndicator and KStatusNotifierItem Support». Sin pystray, cada cambio se avisa con una
notificación de escritorio (`notify-send`) o, si tampoco está, con una línea en la terminal.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from cast_tools_common.reconexion import esperas

logger = logging.getLogger("cast_tools_common.bandeja")

# Del payload de STATE_SYNC: (navegador conectado, detalle para el texto del indicador).
Evaluador = Callable[[Dict[str, Any]], Tuple[bool, str]]

COLORES = {"conectado": (46, 160, 67), "sin_navegador": (210, 153, 34), "sin_daemon": (130, 130, 130)}


@dataclass(frozen=True)
class Estado:
    nivel: str     # "conectado", "sin_navegador" o "sin_daemon"
    detalle: str

    @property
    def color(self) -> Tuple[int, int, int]:
        return COLORES[self.nivel]


SIN_DAEMON = Estado("sin_daemon", "El daemon no responde")


def estado_desde(mensaje: str, evaluar: Evaluador) -> Optional[Estado]:
    """El estado que indica un mensaje del daemon (None si no es un STATE_SYNC)."""
    try:
        datos = json.loads(mensaje)
    except ValueError:
        return None
    if datos.get("action") != "STATE_SYNC":
        return None
    conectado, detalle = evaluar(datos.get("payload") or {})
    return Estado("conectado" if conectado else "sin_navegador", detalle)


async def vigilar(uri: str, evaluar: Evaluador, al_cambiar: Callable[[Estado], None],
                  pin: Optional[str] = None, detener: Optional[asyncio.Event] = None) -> None:
    """Se conecta al daemon (reintentando para siempre) y avisa cada cambio de estado."""
    from websockets.asyncio.client import connect

    actual: Optional[Estado] = None

    def cambiar(nuevo: Estado) -> None:
        nonlocal actual
        if nuevo != actual:
            actual = nuevo
            logger.info("Estado: %s", nuevo.detalle)
            al_cambiar(nuevo)

    detener = detener or asyncio.Event()
    for espera in esperas(inicial=1.0, maximo=30.0):
        if detener.is_set():
            return
        try:
            async with connect(uri, proxy=None, open_timeout=3) as ws:
                if pin:
                    await ws.send(json.dumps({"version": "1.1", "source": "client", "type": "command",
                                              "action": "PAIR_REQUEST", "payload": {"pin": pin}}))
                async for crudo in ws:
                    nuevo = estado_desde(str(crudo), evaluar)
                    if nuevo:
                        cambiar(nuevo)
                    if detener.is_set():
                        return
        except Exception as e:  # noqa: BLE001 - cualquier corte (red, protocolo, cierre) es «sin daemon»
            logger.debug("Sin conexión con %s: %s", uri, e)
        cambiar(SIN_DAEMON)
        try:
            await asyncio.wait_for(detener.wait(), timeout=espera)
            return
        except asyncio.TimeoutError:
            pass


def _icono(color: Tuple[int, int, int]) -> Any:
    from PIL import Image, ImageDraw

    imagen = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(imagen).ellipse((8, 8, 56, 56), fill=(*color, 255))
    return imagen


def notificar(titulo: str, estado: Estado) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", titulo, titulo, estado.detalle], check=False)
    else:
        print(f"[{titulo}] {estado.detalle}", flush=True)


def correr(titulo: str, uri: str, evaluar: Evaluador, pin: Optional[str] = None,
           forzar_notificaciones: bool = False) -> None:
    """Muestra el indicador hasta que el usuario elige «Salir» (o Ctrl+C)."""
    try:
        if forzar_notificaciones:
            raise ImportError
        import pystray
    except ImportError:
        logger.info("Sin pystray: los cambios se avisan con notificaciones")
        try:
            asyncio.run(vigilar(uri, evaluar, lambda e: notificar(titulo, e), pin))
        except KeyboardInterrupt:
            pass
        return

    detener: Optional[asyncio.Event] = None
    lazo: Optional[asyncio.AbstractEventLoop] = None

    def salir(icono: Any, _item: Any) -> None:
        if lazo and detener:
            lazo.call_soon_threadsafe(detener.set)
        icono.stop()

    icono = pystray.Icon(titulo, _icono(SIN_DAEMON.color), f"{titulo}: {SIN_DAEMON.detalle}",
                         menu=pystray.Menu(pystray.MenuItem("Salir", salir)))

    def actualizar(estado: Estado) -> None:
        icono.icon = _icono(estado.color)
        icono.title = f"{titulo}: {estado.detalle}"

    async def principal() -> None:
        nonlocal detener, lazo
        detener, lazo = asyncio.Event(), asyncio.get_running_loop()
        await vigilar(uri, evaluar, actualizar, pin, detener)

    hilo = threading.Thread(target=lambda: asyncio.run(principal()), daemon=True)
    hilo.start()
    try:
        icono.run()
    except KeyboardInterrupt:
        icono.stop()
