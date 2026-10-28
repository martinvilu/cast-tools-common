"""Seguridad del emparejamiento, reconexión, registro, atajos y bandeja (Ola 24)."""

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import InvalidStatus

from cast_tools_common import atajos, bandeja
from cast_tools_common.reconexion import con_reintentos, esperas
from cast_tools_common.registro import configurar_registro, ruta_registro
from cast_tools_common.seguridad import (
    LimitadorIntentos,
    TokensEfimeros,
    conexion_local_confiable,
    es_loopback,
    generar_pin,
    origen_permitido,
    pin_correcto,
    rechazar_origen_web,
)


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_pin_de_seis_digitos_y_comparacion():
    pin = generar_pin()
    assert len(pin) == 6 and pin.isdigit()
    assert pin_correcto(f" {pin} ", pin) and not pin_correcto("000000", pin)
    assert not pin_correcto("", None) and not pin_correcto(None, pin)


def test_los_tokens_vencen_y_se_revocan():
    reloj = Reloj()
    tokens = TokensEfimeros(duracion=10, reloj=reloj)
    t = tokens.emitir("android-1")
    assert len(t) >= 40 and tokens.validar(t) == "android-1"
    assert tokens.validar("otro") is None and tokens.validar(None) is None
    reloj.t = 10
    assert tokens.validar(t) is None and len(tokens) == 0
    t2 = tokens.emitir("cli")
    tokens.revocar(t2)
    assert tokens.validar(t2) is None


def test_limitador_de_intentos():
    reloj = Reloj()
    lim = LimitadorIntentos(maximo=2, ventana=60, reloj=reloj)
    lim.fallo("10.0.0.5")
    assert not lim.bloqueada("10.0.0.5")
    lim.fallo("10.0.0.5")
    assert lim.bloqueada("10.0.0.5") and not lim.bloqueada("10.0.0.6")
    reloj.t = 61
    assert not lim.bloqueada("10.0.0.5")


def test_origenes_y_loopback():
    assert origen_permitido(None) and origen_permitido("moz-extension://abc") and origen_permitido("chrome-extension://x")
    assert not origen_permitido("https://sitio.example") and not origen_permitido("null")
    assert es_loopback("127.0.0.1") and es_loopback("::1") and not es_loopback("192.168.0.10") and not es_loopback("")
    local = SimpleNamespace(remote_address=("127.0.0.1", 5000), request=SimpleNamespace(headers={}))
    pagina = SimpleNamespace(remote_address=("127.0.0.1", 5000),
                             request=SimpleNamespace(headers={"Origin": "https://sitio.example"}))
    lan = SimpleNamespace(remote_address=("192.168.0.10", 5000), request=SimpleNamespace(headers={}))
    assert conexion_local_confiable(local)
    assert not conexion_local_confiable(pagina) and not conexion_local_confiable(lan)


@pytest.mark.asyncio
async def test_un_websocket_abierto_por_una_pagina_recibe_403():
    async def eco(ws):
        async for m in ws:
            await ws.send(m)

    async with serve(eco, "127.0.0.1", 0, process_request=rechazar_origen_web) as servidor:
        puerto = servidor.sockets[0].getsockname()[1]
        with pytest.raises(InvalidStatus) as exc:
            async with connect(f"ws://127.0.0.1:{puerto}", proxy=None, origin="https://sitio.example"):
                pass
        assert exc.value.response.status_code == 403
        async with connect(f"ws://127.0.0.1:{puerto}", proxy=None, origin="moz-extension://abc") as ws:
            await ws.send("hola")
            assert await ws.recv() == "hola"
        async with connect(f"ws://127.0.0.1:{puerto}", proxy=None) as ws:
            await ws.send("cli")
            assert await ws.recv() == "cli"


def test_esperas_exponenciales_con_azar():
    sin_azar = esperas(0.5, 4.0, azar=0)
    assert [next(sin_azar) for _ in range(5)] == [0.5, 1.0, 2.0, 4.0, 4.0]
    con_azar = esperas(1.0, 8.0, azar=0.2, aleatorio=lambda: 1.0)
    assert next(con_azar) == pytest.approx(1.2)


@pytest.mark.asyncio
async def test_con_reintentos(monkeypatch):
    dormir = asyncio.sleep
    monkeypatch.setattr("cast_tools_common.reconexion.asyncio.sleep", lambda s: dormir(0))
    intentos = []

    async def conectar():
        intentos.append(1)
        if len(intentos) < 3:
            raise OSError("red caída")
        return "ok"

    assert await con_reintentos(conectar, reintentos=3) == "ok" and len(intentos) == 3
    intentos.clear()
    with pytest.raises(OSError):
        await con_reintentos(conectar, reintentos=1)


def test_registro_rotativo(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert ruta_registro() == tmp_path / "p1" / "cast.log"
    raiz = logging.getLogger()
    antes = list(raiz.handlers)
    try:
        ruta = configurar_registro("meet-tools", terminal=False)
        logging.getLogger("meet_tools.daemon").info("Extensión conectada")
        for h in raiz.handlers:
            h.flush()
        assert ruta == tmp_path / "p1" / "cast.log"
        assert "meet-tools meet_tools.daemon: Extensión conectada" in ruta.read_text(encoding="utf-8")
    finally:
        for h in raiz.handlers[:]:
            if h not in antes:
                raiz.removeHandler(h)
                h.close()


class FalsoGsettings:
    def __init__(self, lista="@as []"):
        self.valores = {("custom-keybindings",): lista}
        self.llamadas = []

    def __call__(self, args):
        self.llamadas.append(list(args))
        if args[0] == "get":
            return self.valores[("custom-keybindings",)] + "\n"
        if args[0] == "set" and args[2] == "custom-keybindings":
            self.valores[("custom-keybindings",)] = args[3]
        return ""


def test_atajos_en_gnome_conservan_los_del_usuario():
    ajeno = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    g = FalsoGsettings(f"['{ajeno}']")
    mic = atajos.Atajo("p1-meet-mic", "Meet: micrófono", "/usr/bin/meet-tools mic", "<Control><Alt>m")
    atajos.instalar([mic], g)
    assert ["set", f"{atajos.ESQUEMA_ATAJO}:{mic.ruta}", "binding", "<Control><Alt>m"] in g.llamadas
    assert atajos.instalados("p1-meet-", g) == [mic.ruta]
    atajos.instalar([mic], g)  # reinstalar no duplica
    assert g.valores[("custom-keybindings",)].count(mic.ruta) == 1
    assert atajos.quitar("p1-meet-", g) == 1
    assert atajos.instalados("p1-meet-", g) == [] and ajeno in g.valores[("custom-keybindings",)]


def test_combinacion_legible():
    assert atajos.legible("<Control><Alt>m") == "Ctrl+Alt+M"
    assert atajos.legible("<Control><Alt>Page_Down") == "Ctrl+Alt+Page_Down"


def test_estado_de_la_bandeja():
    evaluar = lambda p: (bool(p.get("inCall")), "En llamada" if p.get("inCall") else "Sin llamada")
    msg = json.dumps({"action": "STATE_SYNC", "payload": {"inCall": True}})
    assert bandeja.estado_desde(msg, evaluar) == bandeja.Estado("conectado", "En llamada")
    assert bandeja.estado_desde(json.dumps({"action": "ACK"}), evaluar) is None
    assert bandeja.estado_desde("no es json", evaluar) is None
    assert bandeja.SIN_DAEMON.color != bandeja.Estado("conectado", "").color


@pytest.mark.asyncio
async def test_la_bandeja_sigue_al_daemon():
    estados = []
    detener = asyncio.Event()

    async def daemon(ws):
        await ws.send(json.dumps({"action": "STATE_SYNC", "payload": {"inCall": False}}))
        await ws.send(json.dumps({"action": "STATE_SYNC", "payload": {"inCall": True}}))
        await ws.close()

    def al_cambiar(e):
        estados.append(e.nivel)
        if len(estados) == 3:
            detener.set()

    async with serve(daemon, "127.0.0.1", 0) as servidor:
        puerto = servidor.sockets[0].getsockname()[1]
        await asyncio.wait_for(bandeja.vigilar(f"ws://127.0.0.1:{puerto}", lambda p: (bool(p.get("inCall")), ""),
                                               al_cambiar, detener=detener), timeout=10)
    assert estados == ["sin_navegador", "conectado", "sin_daemon"]


def test_gestionar_atajos():
    g = FalsoGsettings()
    lista = [atajos.Atajo("p1-meet-mic", "Meet: micrófono", "meet-tools mic", "<Control><Alt>m")]
    assert "sin instalar" in "\n".join(atajos.gestionar(lista, "p1-meet-", "mostrar", g, gnome=True))
    assert "✓ 1 atajos instalados" in "\n".join(atajos.gestionar(lista, "p1-meet-", "instalar", g, gnome=True))
    assert "En GNOME: instalados." in atajos.gestionar(lista, "p1-meet-", "mostrar", g, gnome=True)
    assert atajos.gestionar(lista, "p1-meet-", "quitar", g, gnome=True) == ["✓ 1 atajos quitados."]
    otro = atajos.gestionar(lista, "p1-meet-", "instalar", g, gnome=False)
    assert "sólo funciona en GNOME" in otro[0] and "Ctrl+Alt+M" in otro[2]
