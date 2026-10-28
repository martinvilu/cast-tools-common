"""Atajos de teclado globales para meet-tools y slide-tools (Ola 24).

Bajo Wayland un programa no puede capturar teclas globales: lo hace el escritorio. Cada
atajo corre un comando de una sola vez (`meet-tools mic`, `slide-tools next`) que habla con
el daemon, así el docente controla la llamada o las diapositivas sin sacar el foco de la
terminal ni de la presentación.

En GNOME se registran como atajos personalizados con `gsettings`, bajo rutas `p1-…` para
poder listarlos y quitarlos sin tocar los del usuario. En otros escritorios se muestran los
comandos para cargarlos a mano.
"""

from __future__ import annotations

import ast
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable, List, Sequence

ESQUEMA = "org.gnome.settings-daemon.plugins.media-keys"
ESQUEMA_ATAJO = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
RUTA_BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

# Recibe los argumentos de gsettings y devuelve su salida estándar.
Ejecutor = Callable[[Sequence[str]], str]


@dataclass(frozen=True)
class Atajo:
    clave: str        # identificador estable: p1-meet-mic
    nombre: str       # lo que muestra Configuración → Teclado
    comando: str
    combinacion: str  # en la sintaxis de GNOME: <Control><Alt>m

    @property
    def ruta(self) -> str:
        return f"{RUTA_BASE}{self.clave}/"


def gsettings(args: Sequence[str]) -> str:
    res = subprocess.run(["gsettings", *args], capture_output=True, text=True, check=True)
    return res.stdout


def es_gnome() -> bool:
    return "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() and shutil.which("gsettings") is not None


def comando_de(herramienta: str, *args: str) -> str:
    """El comando con la ruta absoluta del ejecutable: el escritorio no tiene el PATH de la terminal."""
    ejecutable = shutil.which(herramienta) or herramienta
    return shlex.join([ejecutable, *args])


def _lista(ejecutar: Ejecutor) -> List[str]:
    salida = ejecutar(["get", ESQUEMA, "custom-keybindings"]).strip()
    if salida.startswith("@as"):
        salida = salida[3:].strip()
    valor = ast.literal_eval(salida) if salida else []
    return [str(r) for r in valor]


def _guardar_lista(ejecutar: Ejecutor, rutas: Sequence[str]) -> None:
    ejecutar(["set", ESQUEMA, "custom-keybindings", str(list(rutas))])


def instalados(prefijo: str, ejecutar: Ejecutor = gsettings) -> List[str]:
    """Rutas de los atajos registrados con ese prefijo (`p1-meet-`)."""
    return [r for r in _lista(ejecutar) if r.startswith(f"{RUTA_BASE}{prefijo}")]


def instalar(atajos: Sequence[Atajo], ejecutar: Ejecutor = gsettings) -> None:
    rutas = _lista(ejecutar)
    for a in atajos:
        relocatable = f"{ESQUEMA_ATAJO}:{a.ruta}"
        ejecutar(["set", relocatable, "name", a.nombre])
        ejecutar(["set", relocatable, "command", a.comando])
        ejecutar(["set", relocatable, "binding", a.combinacion])
        if a.ruta not in rutas:
            rutas.append(a.ruta)
    _guardar_lista(ejecutar, rutas)


def quitar(prefijo: str, ejecutar: Ejecutor = gsettings) -> int:
    """Quita los atajos con ese prefijo; devuelve cuántos había."""
    rutas = _lista(ejecutar)
    propias = [r for r in rutas if r.startswith(f"{RUTA_BASE}{prefijo}")]
    for ruta in propias:
        for clave in ("name", "command", "binding"):
            ejecutar(["reset", f"{ESQUEMA_ATAJO}:{ruta}", clave])
    if propias:
        _guardar_lista(ejecutar, [r for r in rutas if r not in propias])
    return len(propias)


def legible(combinacion: str) -> str:
    """`<Control><Alt>m` → `Ctrl+Alt+M`."""
    nombres = {"Control": "Ctrl", "Alt": "Alt", "Shift": "Mayús", "Super": "Super"}
    partes = [nombres.get(m, m) for m in combinacion.replace(">", "<").split("<") if m]
    *mods, tecla = partes
    return "+".join([*mods, tecla.upper() if len(tecla) == 1 else tecla])
