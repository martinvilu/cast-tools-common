"""Comportamiento de la API pública de cast-tools-common (N-CAST-01).

Sin red ni web-ext: las llamadas a `web-ext` y a Zeroconf se reemplazan.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import cast_tools_common.discovery as discovery
import cast_tools_common.signer as signer
from cast_tools_common import (
    MdnsPublisher,
    build_pairing_uri,
    generate_qr_svg,
    get_local_ip,
    pack_web_extension,
    prepare_firefox_staging,
    sign_firefox_addon,
)


@pytest.fixture
def extension(tmp_path: Path) -> Path:
    ext = tmp_path / "extension"
    (ext / "icons").mkdir(parents=True)
    (ext / "manifest.json").write_text(json.dumps({"name": "demo", "version": "2.3.4",
                                                   "background": {"service_worker": "background.js"}}),
                                       encoding="utf-8")
    (ext / "background.js").write_text("console.log('bg');", encoding="utf-8")
    (ext / "icons" / "i.png").write_bytes(b"png")
    (ext / ".oculto").write_text("x", encoding="utf-8")
    (ext / "tmp.swp").write_text("x", encoding="utf-8")
    return ext


# --- packer ------------------------------------------------------------------------------

def _manifiesto(archivo: Path) -> dict:
    with zipfile.ZipFile(archivo) as zf:
        return json.loads(zf.read("manifest.json"))


def test_pack_adapta_el_manifiesto_a_cada_navegador(extension, tmp_path):
    res = pack_web_extension(extension, tmp_path / "dist", target="both", addon_id="demo@p1", addon_slug="demo")
    assert res["chrome"].name == "demo-chrome-v2.3.4.zip"
    assert res["firefox"].name == "demo-firefox-v2.3.4.xpi"

    chrome = _manifiesto(res["chrome"])
    assert chrome["background"] == {"service_worker": "background.js"}
    assert "browser_specific_settings" not in chrome

    firefox = _manifiesto(res["firefox"])
    assert firefox["background"] == {"scripts": ["background.js"]}
    assert firefox["browser_specific_settings"]["gecko"]["id"] == "demo@p1"

    nombres = zipfile.ZipFile(res["chrome"]).namelist()
    assert "icons/i.png" in nombres and ".oculto" not in nombres


def test_pack_un_solo_destino_y_errores(extension, tmp_path):
    assert list(pack_web_extension(extension, tmp_path / "d", target="chrome")) == ["chrome"]
    with pytest.raises(ValueError):
        pack_web_extension(None)
    with pytest.raises(FileNotFoundError):
        pack_web_extension(tmp_path)  # sin manifest.json


# --- signer ------------------------------------------------------------------------------

def test_staging_copia_la_extension_y_agrega_gecko(extension, tmp_path):
    staging = prepare_firefox_staging(extension, tmp_path / "staging", addon_id="demo@p1",
                                      firefox_background_scripts=True)
    manifiesto = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
    assert manifiesto["browser_specific_settings"]["gecko"]["id"] == "demo@p1"
    assert manifiesto["background"] == {"scripts": ["background.js"]}
    assert (staging / "icons" / "i.png").exists()
    assert not (staging / ".oculto").exists() and not (staging / "tmp.swp").exists()
    with pytest.raises(FileNotFoundError):
        prepare_firefox_staging(tmp_path / "no_existe", tmp_path / "s2")


class WebExtFalso:
    """Reemplaza subprocess.run para `web-ext lint` y `web-ext sign`."""

    def __init__(self, lint_rc=0, sign_rc=0, genera_xpi=True):
        self.lint_rc, self.sign_rc, self.genera_xpi = lint_rc, sign_rc, genera_xpi
        self.llamadas: list[list[str]] = []

    def __call__(self, cmd, **_kw):
        self.llamadas.append(cmd)
        if cmd[1] == "lint":
            return SimpleNamespace(returncode=self.lint_rc, stdout="lint", stderr="")
        if self.genera_xpi:
            artefactos = Path(cmd[cmd.index("--artifacts-dir") + 1])
            (artefactos / "firmado.xpi").write_bytes(b"xpi")
        return SimpleNamespace(returncode=self.sign_rc, stdout="firmado", stderr="error de AMO")


@pytest.fixture
def web_ext(monkeypatch):
    def instalar(**opciones):
        falso = WebExtFalso(**opciones)
        monkeypatch.setattr(subprocess, "run", falso)
        return falso
    monkeypatch.delenv("WEB_EXT_API_KEY", raising=False)
    monkeypatch.delenv("WEB_EXT_API_SECRET", raising=False)
    monkeypatch.delenv("AMO_JWT_ISSUER", raising=False)
    monkeypatch.delenv("AMO_JWT_SECRET", raising=False)
    return instalar


def test_firma_exitosa(web_ext, extension, tmp_path):
    falso = web_ext()
    res = sign_firefox_addon(extension, tmp_path / "dist", api_key="k", api_secret="s", addon_slug="demo")
    assert res["status"] == "signed"
    assert Path(res["signed_file"]).name == "demo-v2.3.4-signed.xpi" and Path(res["signed_file"]).exists()
    assert [c[1] for c in falso.llamadas] == ["lint", "sign"]


def test_lint_fallido_detiene_la_firma(web_ext, extension, tmp_path):
    web_ext(lint_rc=1)
    with pytest.raises(RuntimeError, match="web-ext lint"):
        sign_firefox_addon(extension, tmp_path / "dist", api_key="k", api_secret="s")
    assert sign_firefox_addon(extension, tmp_path / "dist", lint_only=True)["status"] == "lint_failed"


def test_simulacion_y_credenciales(web_ext, extension, tmp_path, monkeypatch):
    web_ext()
    res = sign_firefox_addon(extension, tmp_path / "dist", dry_run=True)
    assert res["status"] == "dry_run" and res["credentials_present"] is False
    assert "<AMO_API_KEY>" in res["command"]
    with pytest.raises(ValueError, match="Credenciales de Mozilla AMO ausentes"):
        sign_firefox_addon(extension, tmp_path / "dist")
    monkeypatch.setenv("WEB_EXT_API_KEY", "k")
    monkeypatch.setenv("WEB_EXT_API_SECRET", "s")
    assert sign_firefox_addon(extension, tmp_path / "dist", dry_run=True)["credentials_present"] is True


def test_firma_rechazada_o_sin_xpi(web_ext, extension, tmp_path):
    web_ext(sign_rc=1)
    with pytest.raises(RuntimeError, match="código 1"):
        sign_firefox_addon(extension, tmp_path / "dist", api_key="k", api_secret="s")
    web_ext(genera_xpi=False)
    with pytest.raises(FileNotFoundError):
        sign_firefox_addon(extension, tmp_path / "dist", api_key="k", api_secret="s")


# --- discovery ---------------------------------------------------------------------------

def test_uri_de_emparejamiento_y_qr():
    uri = build_pairing_uri("meet", "10.0.0.5", 8765, "123456", name="aula")
    assert uri == "bridge://pair?v=1.3&host=10.0.0.5&port=8765&service=meet&pin=123456&name=aula"
    assert "<svg" in generate_qr_svg(uri)


def test_ip_local_de_respaldo_sin_red(monkeypatch):
    class SocketSinRed:
        def __init__(self, *_a):
            pass

        def connect(self, _destino):
            raise OSError("sin red")

        def close(self):
            pass

    monkeypatch.setattr(discovery.socket, "socket", SocketSinRed)
    assert get_local_ip() == "127.0.0.1"


class ZeroconfFalso:
    def __init__(self, falla=False):
        self.falla = falla
        self.registrado = self.cerrado = False

    async def async_register_service(self, _info):
        if self.falla:
            raise OSError("sin multicast")
        self.registrado = True

    async def async_unregister_service(self, _info):
        self.registrado = False

    async def async_close(self):
        self.cerrado = True


@pytest.mark.parametrize("falla", [False, True])
def test_publicacion_mdns(monkeypatch, falla):
    zc = ZeroconfFalso(falla)
    monkeypatch.setattr(discovery, "AsyncZeroconf", lambda: zc)
    publicador = MdnsPublisher("aula-1", "_meet._tcp.local", 8765, {"v": 1}, host_ip="10.0.0.5")
    assert publicador.service_type == "_meet._tcp.local."
    assert asyncio.run(publicador.start()) is (not falla)
    if falla:
        assert zc.cerrado  # libera Zeroconf y sigue en modo directo
    else:
        asyncio.run(publicador.stop())
        assert zc.cerrado and not zc.registrado
