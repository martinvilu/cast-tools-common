import pytest
from cast_tools_common.discovery import get_local_ip, build_pairing_uri, generate_qr_ascii, generate_qr_svg
from cast_tools_common.packer import pack_web_extension
from cast_tools_common.signer import prepare_firefox_staging, run_web_ext_lint

def test_discovery_uri_and_qr():
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0

    uri = build_pairing_uri("test", "127.0.0.1", 8080, "1234", name="myhost")
    assert "bridge://pair" in uri
    assert "pin=1234" in uri

    qr_ascii = generate_qr_ascii(uri)
    assert len(qr_ascii) > 0

    qr_svg = generate_qr_svg(uri)
    assert "<svg" in qr_svg

def test_packer_and_signer_staging(tmp_path):
    ext_dir = tmp_path / "extension"
    ext_dir.mkdir()
    (ext_dir / "manifest.json").write_text('{"name": "test", "version": "1.0.0"}', encoding="utf-8")
    (ext_dir / "background.js").write_text('console.log("bg");', encoding="utf-8")

    out_dir = tmp_path / "dist"
    res = pack_web_extension(
        extension_dir=ext_dir,
        output_dir=out_dir,
        target="both",
        addon_id="test@dev",
        addon_slug="test-tool",
    )
    assert "chrome" in res
    assert "firefox" in res
    assert res["chrome"].exists()
    assert res["firefox"].exists()

    staging_dir = tmp_path / "staging"
    staged = prepare_firefox_staging(ext_dir, staging_dir, addon_id="test@dev")
    assert (staged / "manifest.json").exists()
