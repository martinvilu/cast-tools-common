"""Infraestructura común para validación y firma digital de WebExtensions con web-ext de Mozilla."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Dict, Optional, Tuple


def prepare_firefox_staging(
    extension_dir: Path,
    staging_dir: Path,
    addon_id: str = "bridge@local.dev",
    firefox_background_scripts: bool = True,
) -> Path:
    """Prepara un directorio temporal con el manifiesto adaptado según las reglas de firma de Mozilla."""
    if not extension_dir.exists():
        raise FileNotFoundError(f"Directorio de extensión no encontrado: {extension_dir}")

    staging_dir.mkdir(parents=True, exist_ok=True)

    for item in extension_dir.rglob("*"):
        if item.is_file() and not item.name.startswith(".") and item.suffix not in (".swp", ".tmp", ".pyc"):
            rel_path = item.relative_to(extension_dir)
            dest = staging_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)

    # Adaptar manifest.json para Firefox MV3
    manifest_path = staging_dir / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    if firefox_background_scripts:
        manifest["background"] = {
            "scripts": ["background.js"]
        }
    manifest["browser_specific_settings"] = {
        "gecko": {
            "id": addon_id,
            "strict_min_version": "142.0",
            "data_collection_permissions": {
                "required": ["none"]
            }
        }
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return staging_dir


def run_web_ext_lint(source_dir: Path) -> Tuple[bool, str]:
    """Ejecuta web-ext lint sobre el directorio de extensión preparado."""
    cmd = ["web-ext", "lint", "-s", str(source_dir), "--no-config-discovery"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    success = (res.returncode == 0)
    output = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
    return success, output.strip()


def sign_firefox_addon(
    extension_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    channel: str = "unlisted",  # "unlisted" o "listed"
    timeout_ms: int = 600000,
    lint_only: bool = False,
    dry_run: bool = False,
    addon_id: str = "bridge@local.dev",
    addon_slug: str = "bridge",
    firefox_background_scripts: bool = True,
) -> Dict[str, object]:
    """Valida sintácticamente y solicita la firma criptográfica en Mozilla Add-ons (AMO)."""
    if extension_dir is None:
        raise ValueError("extension_dir debe ser especificado.")

    ext_path = extension_dir
    out_path = output_dir or (ext_path.parent / "dist")
    out_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_dir = Path(tmp_dir) / "staging"
        artifacts_dir = Path(tmp_dir) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        prepare_firefox_staging(
            ext_path,
            staging_dir,
            addon_id=addon_id,
            firefox_background_scripts=firefox_background_scripts,
        )

        lint_success, lint_out = run_web_ext_lint(staging_dir)
        if not lint_success and not dry_run:
            return {
                "success": False,
                "output": f"Fallo en la validación de web-ext lint:\n{lint_out}",
                "artifact": None
            }

        if lint_only:
            return {
                "success": lint_success,
                "output": lint_out or "Validación sintáctica exitosa sin errores.",
                "artifact": None
            }

        key = api_key or os.environ.get("WEB_EXT_API_KEY") or os.environ.get("AMO_JWT_ISSUER")
        secret = api_secret or os.environ.get("WEB_EXT_API_SECRET") or os.environ.get("AMO_JWT_SECRET")

        if not key or not secret:
            if dry_run:
                key = "dry-run-key"
                secret = "dry-run-secret"
            else:
                return {
                    "success": False,
                    "output": "No se encontraron credenciales de Mozilla AMO (defina WEB_EXT_API_KEY y WEB_EXT_API_SECRET).",
                    "artifact": None
                }

        cmd = [
            "web-ext", "sign",
            "-s", str(staging_dir),
            "-a", str(artifacts_dir),
            "--api-key", key,
            "--api-secret", secret,
            "--channel", channel,
            "--timeout", str(timeout_ms),
            "--no-config-discovery"
        ]

        if dry_run:
            return {
                "success": True,
                "output": f"[DRY-RUN] Manifiesto preparado correctamente en {staging_dir}.\nComando a ejecutar:\n" + " ".join(cmd),
                "artifact": None
            }

        proc = subprocess.run(cmd, capture_output=True, text=True)
        combined_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

        if proc.returncode != 0:
            return {
                "success": False,
                "output": f"Error durante la firma en Mozilla AMO:\n{combined_output.strip()}",
                "artifact": None
            }

        manifest_path = staging_dir / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            version = json.load(f).get("version", "1.0.0")

        signed_files = list(artifacts_dir.glob("*.xpi"))
        if not signed_files:
            raise FileNotFoundError("web-ext sign finalizó sin generar un archivo .xpi firmado en los artefactos.")

        signed_src = signed_files[0]
        final_dest = out_path / f"{addon_slug}-v{version}-signed.xpi"
        shutil.copy2(signed_src, final_dest)

        return {
            "success": True,
            "output": combined_output.strip(),
            "artifact": str(final_dest)
        }
