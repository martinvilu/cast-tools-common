"""Módulo de empaquetado para distribución de WebExtensions (Chrome ZIP y Firefox XPI)."""

import json
from pathlib import Path
import shutil
from typing import Dict, Optional
import zipfile


def pack_web_extension(
    extension_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    target: str = "both",  # "chrome", "firefox", "both"
    addon_id: str = "bridge@local.dev",
    addon_slug: str = "bridge",
    firefox_background_scripts: bool = True,
) -> Dict[str, Path]:
    """Genera paquetes .zip para Chrome y .xpi / .zip para Firefox con manifiestos adaptados."""
    ext_path = extension_dir
    if ext_path is None:
        raise ValueError("extension_dir debe ser especificado.")

    out_path = output_dir or (ext_path.parent / "dist")
    out_path.mkdir(parents=True, exist_ok=True)

    manifest_file = ext_path / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"No se encontró manifest.json en: {ext_path}")

    with open(manifest_file, "r", encoding="utf-8") as f:
        base_manifest = json.load(f)

    version = base_manifest.get("version", "1.0.0")
    results = {}

    targets = ["chrome", "firefox"] if target == "both" else [target]

    for tgt in targets:
        manifest_copy = json.loads(json.dumps(base_manifest))

        if tgt == "firefox":
            if firefox_background_scripts:
                manifest_copy["background"] = {
                    "scripts": ["background.js"]
                }
            manifest_copy["browser_specific_settings"] = {
                "gecko": {
                    "id": addon_id,
                    "strict_min_version": "142.0",
                    "data_collection_permissions": {
                        "required": ["none"]
                    }
                }
            }
            archive_name = f"{addon_slug}-firefox-v{version}.xpi"
        else:
            manifest_copy["background"] = {
                "service_worker": "background.js"
            }
            manifest_copy.pop("browser_specific_settings", None)
            archive_name = f"{addon_slug}-chrome-v{version}.zip"

        archive_path = out_path / archive_name
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in ext_path.rglob("*"):
                if item.is_file() and not item.name.startswith("."):
                    rel_path = item.relative_to(ext_path)
                    if rel_path.name == "manifest.json":
                        zf.writestr("manifest.json", json.dumps(manifest_copy, indent=2, ensure_ascii=False))
                    else:
                        zf.write(item, rel_path)

        results[tgt] = archive_path

    return results
