"""Espera exponencial con azar para reconectar (QoL #608, Ola 24).

meet-tools y slide-tools tenían cada uno su lazo de 0,5 s, 1 s, 2 s… sin azar: si se corta
la red del aula, todos los clientes reintentan en el mismo instante. Las extensiones ya
usaban azar; acá queda el mismo criterio para los clientes de Python.
"""

from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, Iterator, Tuple, Type, TypeVar

T = TypeVar("T")


def esperas(inicial: float = 0.5, maximo: float = 8.0, azar: float = 0.2,
            aleatorio: Callable[[], float] = random.random) -> Iterator[float]:
    """0,5 s, 1 s, 2 s… hasta `maximo`, cada una corrida hasta ±`azar` (proporción)."""
    base = inicial
    while True:
        yield max(0.0, base * (1 + azar * (2 * aleatorio() - 1)))
        base = min(base * 2, maximo)


async def con_reintentos(conectar: Callable[[], Awaitable[T]], reintentos: int,
                         errores: Tuple[Type[BaseException], ...] = (OSError, asyncio.TimeoutError),
                         inicial: float = 0.5, maximo: float = 8.0) -> T:
    """Llama a `conectar` hasta `reintentos` veces más si falla con uno de `errores`."""
    for intento, espera in enumerate(esperas(inicial, maximo)):
        try:
            return await conectar()
        except errores:
            if intento >= reintentos:
                raise
            await asyncio.sleep(espera)
    raise AssertionError("inalcanzable")  # esperas() es infinito
