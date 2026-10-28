"""Registro rotativo común en `~/.local/state/p1/cast.log` (Ola 24).

Los daemons escribían sólo en la terminal: si se cerraba, no quedaba rastro de cuándo se
desconectó la extensión o quién intentó emparejarse. Los dos escriben en el mismo archivo
(con el nombre de la herramienta en cada línea), que rota a 1 MB y guarda tres anteriores.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

TAMANO_MAXIMO = 1_000_000
COPIAS = 3
_FORMATO = "%(asctime)s [%(levelname)s] {herramienta} %(name)s: %(message)s"


def ruta_registro() -> Path:
    """`$XDG_STATE_HOME/p1/cast.log` (por omisión `~/.local/state/p1/cast.log`)."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "p1" / "cast.log"


def configurar_registro(herramienta: str, nivel: int = logging.INFO, ruta: Optional[Path] = None,
                        terminal: bool = True) -> Optional[Path]:
    """Registro en la terminal y en el archivo rotativo; devuelve la ruta (None si no se pudo abrir)."""
    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    formato = logging.Formatter(_FORMATO.format(herramienta=herramienta))
    if terminal and not any(getattr(h, "_cast_terminal", False) for h in raiz.handlers):
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        consola._cast_terminal = True  # type: ignore[attr-defined]
        raiz.addHandler(consola)

    destino = ruta or ruta_registro()
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        archivo = RotatingFileHandler(destino, maxBytes=TAMANO_MAXIMO, backupCount=COPIAS, encoding="utf-8")
    except OSError as e:
        logging.getLogger("cast_tools_common").warning("No se pudo abrir el registro %s: %s", destino, e)
        return None
    archivo.setFormatter(formato)
    raiz.addHandler(archivo)
    return destino
