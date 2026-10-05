"""`cast-sign` reemplaza a scripts/sign_firefox_addons.sh."""

import json

import pytest

import cast_tools_common.signer as signer
from cast_tools_common.firmar import cargar_env, main


def _extension(raiz, nombre):
    ext = raiz / nombre / "extension"
    ext.mkdir(parents=True)
    (ext / "manifest.json").write_text(json.dumps({"manifest_version": 3, "name": nombre, "version": "1.0",
                                                   "background": {"service_worker": "bg.js"}}), encoding="utf-8")
    (ext / "bg.js").write_text("", encoding="utf-8")


def test_dry_run_de_los_dos(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(signer, "run_web_ext_lint", lambda d: (True, "ok"))
    for nombre in ("meet-tools", "slide-tools"):
        _extension(tmp_path, nombre)
    assert main(["--all", "--dry-run", "--raiz", str(tmp_path)]) == 0
    salida = capsys.readouterr().out
    assert "meet-tools: dry_run" in salida and "slide-tools: dry_run" in salida and "web-ext sign" in salida


def test_falta_la_extension_y_desconocido(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(signer, "run_web_ext_lint", lambda d: (True, "ok"))
    assert main(["slide-tools", "--dry-run", "--raiz", str(tmp_path)]) == 1
    with pytest.raises(SystemExit):
        main(["otro", "--raiz", str(tmp_path)])


def test_env(tmp_path, monkeypatch):
    monkeypatch.delenv("WEB_EXT_API_KEY", raising=False)
    (tmp_path / ".env").write_text('# credenciales\nexport WEB_EXT_API_KEY="user:1"\n', encoding="utf-8")
    cargar_env(tmp_path / ".env")
    import os
    assert os.environ["WEB_EXT_API_KEY"] == "user:1"
