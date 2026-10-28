"""Emparejamiento seguro de los daemons de meet-tools y slide-tools (Ola 24).

- `generar_pin` y `pin_correcto`: PIN de 6 dígitos con `secrets`, comparado en tiempo constante.
- `TokensEfimeros`: al emparejarse con el PIN, el cliente recibe un token aleatorio que vence;
  con él se reconecta (red del aula que se corta, pestaña que se recarga) sin volver a pedir
  el PIN. Viven en memoria: reiniciar el daemon los invalida a todos.
- `origen_permitido` y `rechazar_origen_web`: un WebSocket a 127.0.0.1 lo puede abrir cualquier
  página que el docente tenga abierta. El navegador manda el `Origin` del sitio; sólo se aceptan
  conexiones sin `Origin` (CLI, app Android, ESP32) o desde una extensión.
- `es_loopback`: una conexión local sin origen web es un programa del mismo usuario (la CLI, un
  atajo de teclado, la bandeja) y no necesita PIN; el PIN protege la red del aula.
- `LimitadorIntentos`: cinco PIN equivocados por minuto y por IP.
"""

from __future__ import annotations

import hmac
import ipaddress
import secrets
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Callable, Dict, List, Optional, Sequence

ORIGENES_DE_EXTENSION = ("chrome-extension://", "moz-extension://", "safari-web-extension://")
DURACION_TOKEN = 8 * 3600  # una jornada de clases


def generar_pin() -> str:
    """PIN de emparejamiento de 6 dígitos con un generador criptográfico (N-MEET-02)."""
    return f"{secrets.randbelow(900_000) + 100_000}"


def pin_correcto(recibido: Any, esperado: Optional[str]) -> bool:
    """Compara en tiempo constante: el tiempo de respuesta no revela cuántos dígitos coinciden."""
    if not esperado:
        return False
    return hmac.compare_digest(str(recibido or "").strip().encode(), str(esperado).strip().encode())


def es_loopback(ip: Optional[str]) -> bool:
    if not ip:
        return False
    try:
        return ipaddress.ip_address(ip.split("%")[0]).is_loopback
    except ValueError:
        return ip == "localhost"


def origen_permitido(origen: Optional[str], extra: Sequence[str] = ()) -> bool:
    """Sin `Origin` (un programa), el de una extensión o uno de `extra`; nunca otra página web.

    `extra` es para una extensión que abre el WebSocket desde su content script: el navegador
    manda el origen de la página donde corre (meet-tools: `https://meet.google.com`).
    """
    return origen is None or origen.startswith(ORIGENES_DE_EXTENSION) or origen in extra


def filtro_de_origen(*extra: str) -> Callable[[Any, Any], Any]:
    """`process_request` para `websockets.serve`: 403 a los WebSocket abiertos por otra página."""
    def filtrar(connection: Any, request: Any) -> Any:
        if origen_permitido(request.headers.get("Origin"), extra):
            return None
        return connection.respond(HTTPStatus.FORBIDDEN, "Origen no permitido: sólo la extensión o clientes locales.\n")
    return filtrar


rechazar_origen_web = filtro_de_origen()


def ip_remota(websocket: Any) -> str:
    try:
        return str(websocket.remote_address[0])
    except (AttributeError, IndexError, TypeError):
        return ""


def origen_de(websocket: Any) -> Optional[str]:
    try:
        return websocket.request.headers.get("Origin")
    except AttributeError:
        return None


def conexion_local_confiable(websocket: Any, extra: Sequence[str] = ()) -> bool:
    """Un programa local (sin origen web): la CLI, un atajo de teclado, la bandeja o la extensión."""
    return es_loopback(ip_remota(websocket)) and origen_permitido(origen_de(websocket), extra)


@dataclass
class _Token:
    cliente: str
    vence: float


class TokensEfimeros:
    """Tokens de reconexión que se emiten al emparejarse con el PIN y vencen solos."""

    def __init__(self, duracion: float = DURACION_TOKEN, reloj: Callable[[], float] = time.monotonic):
        self.duracion = duracion
        self._reloj = reloj
        self._tokens: Dict[str, _Token] = {}

    def emitir(self, cliente: str) -> str:
        self._purgar()
        token = secrets.token_urlsafe(32)
        self._tokens[token] = _Token(cliente, self._reloj() + self.duracion)
        return token

    def validar(self, token: Any) -> Optional[str]:
        """El cliente al que se emitió el token, o None si no existe o venció."""
        if not isinstance(token, str) or not token:
            return None
        self._purgar()
        for conocido, datos in self._tokens.items():
            if hmac.compare_digest(conocido.encode(), token.encode()):
                return datos.cliente
        return None

    def revocar(self, token: str) -> None:
        self._tokens.pop(token, None)

    def revocar_todos(self) -> None:
        self._tokens.clear()

    def __len__(self) -> int:
        self._purgar()
        return len(self._tokens)

    def _purgar(self) -> None:
        ahora = self._reloj()
        for token in [t for t, d in self._tokens.items() if d.vence <= ahora]:
            del self._tokens[token]


class LimitadorIntentos:
    """Bloquea una IP tras `maximo` PIN equivocados en `ventana` segundos."""

    def __init__(self, maximo: int = 5, ventana: float = 60.0, reloj: Callable[[], float] = time.monotonic):
        self.maximo = maximo
        self.ventana = ventana
        self._reloj = reloj
        self._fallos: Dict[str, List[float]] = {}

    def bloqueada(self, ip: str) -> bool:
        ahora = self._reloj()
        recientes = [t for t in self._fallos.get(ip, []) if ahora - t < self.ventana]
        self._fallos[ip] = recientes
        return len(recientes) >= self.maximo

    def fallo(self, ip: str) -> None:
        self._fallos.setdefault(ip, []).append(self._reloj())

    def exito(self, ip: str) -> None:
        self._fallos.pop(ip, None)
