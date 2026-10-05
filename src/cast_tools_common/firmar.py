"""`cast-sign`: firma las extensiones de Firefox de meet-tools y slide-tools (revisión 07).

Reemplaza a `scripts/sign_firefox_addons.sh`, que estaba suelto en `dev/tools` y repetía lo que
hacen `meet-tools sign` y `slide-tools sign`: con el firmador compartido de acá, uno o los dos
complementos de una vez.

    cast-sign --all --dry-run
    cast-sign --channel unlisted slide-tools

Las credenciales de AMO salen de --api-key/--api-secret, de WEB_EXT_API_KEY/WEB_EXT_API_SECRET (o
AMO_JWT_ISSUER/AMO_JWT_SECRET) o de un `.env` en la raíz.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from cast_tools_common.signer import sign_firefox_addon

COMPLEMENTOS: Dict[str, str] = {"meet-tools": "meet-bridge@local.dev", "slide-tools": "slide-bridge@local.dev"}


def cargar_env(ruta: Path) -> None:
    """Variables de un `.env` (CLAVE=valor), sin pisar las que ya están en el entorno."""
    if not ruta.is_file():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.removeprefix("export ").split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="cast-sign", description="Firma las extensiones de Firefox de meet-tools y slide-tools con web-ext.")
    parser.add_argument("complementos", nargs="*", metavar="COMPLEMENTO",
                        help=f"Cuáles firmar ({', '.join(COMPLEMENTOS)}); sin ninguno, todos.")
    parser.add_argument("-a", "--all", action="store_true", help="Firmar todos.")
    parser.add_argument("-l", "--lint-only", action="store_true", help="Solo validar con web-ext lint.")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Validar e imprimir el comando, sin enviar.")
    parser.add_argument("-c", "--channel", choices=("unlisted", "listed"), default="unlisted")
    parser.add_argument("--api-key")
    parser.add_argument("--api-secret")
    parser.add_argument("--raiz", type=Path, default=Path.cwd(), help="Directorio que contiene meet-tools/ y slide-tools/.")
    args = parser.parse_args(argv)

    cargar_env(args.raiz / ".env")
    elegidos = list(COMPLEMENTOS) if args.all or not args.complementos else args.complementos
    desconocidos = [c for c in elegidos if c not in COMPLEMENTOS]
    if desconocidos:
        parser.error(f"complemento desconocido: {', '.join(desconocidos)} (válidos: {', '.join(COMPLEMENTOS)})")
    codigo = 0
    for nombre in elegidos:
        extension = args.raiz / nombre / "extension"
        if not extension.is_dir():
            print(f"✗ {nombre}: no existe {extension}", file=sys.stderr)
            codigo = 1
            continue
        try:
            res = sign_firefox_addon(extension_dir=extension, output_dir=args.raiz / nombre / "dist",
                                     api_key=args.api_key, api_secret=args.api_secret, channel=args.channel,
                                     lint_only=args.lint_only, dry_run=args.dry_run, addon_id=COMPLEMENTOS[nombre],
                                     addon_slug=nombre, firefox_background_scripts=True)
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"✗ {nombre}: {exc}", file=sys.stderr)
            codigo = 1
            continue
        estado = res.get("status")
        detalle = res.get("command") or res.get("signed_file") or res.get("lint_output", "")
        print(f"✓ {nombre}: {estado}" + (f"\n  {detalle}" if detalle else ""))
        if estado == "lint_failed":
            codigo = 1
    return codigo


if __name__ == "__main__":
    sys.exit(main())
