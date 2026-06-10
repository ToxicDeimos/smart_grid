"""Calculo del precio de liquidacion de un futures grid (long / short / neutral).

Usa el modelo derivado durante el diseno: la posicion inicial abierta al activar el
grid es la fraccion del rango que queda en la direccion de las ordenes de salida, y la
liquidacion se estima con el precio medio de entrada cuando el grid esta lleno.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GridLiquidation:
    side: str
    avg_entry: float
    liq_price: float
    initial_fraction: float   # fraccion del nocional abierta al activar el grid
    leverage: float


def initial_fraction(entry: float, lower: float, upper: float, side: str = "long") -> float:
    """Fraccion del nocional que se abre como posicion inicial al activar el grid.

    En un grid long, para poder vender en las subidas el bot abre de entrada el inventario
    de todas las ordenes de venta por encima del precio de activacion. Cuanto mas alto el
    techo respecto al precio de entrada, mayor la posicion inicial (y la liquidacion sube).
    """
    span = upper - lower
    if span <= 0:
        return 1.0
    frac = (upper - entry) / span if side == "long" else (entry - lower) / span
    return max(0.0, min(1.0, frac))


def estimate(side: str, lower: float, upper: float, leverage: float,
             entry: float | None = None, mmr: float = 0.005) -> GridLiquidation:
    """Estima la liquidacion del grid cuando esta completamente desplegado (peor caso).

    long  : precio cae hasta 'lower'; entrada media = (activacion + lower)/2.
    short : precio sube hasta 'upper'; entrada media = (activacion + upper)/2.
    neutral: se reporta el lado largo (caida) como referencia conservadora.
    """
    if side == "long":
        entry = entry if entry is not None else upper
        avg = (entry + lower) / 2
        liq = avg * (1 - 1 / leverage + mmr)
        frac = initial_fraction(entry, lower, upper, "long")
    elif side == "short":
        entry = entry if entry is not None else lower
        avg = (entry + upper) / 2
        liq = avg * (1 + 1 / leverage - mmr)
        frac = initial_fraction(entry, lower, upper, "short")
    else:  # neutral
        entry = entry if entry is not None else (upper + lower) / 2
        avg = entry
        liq = ((entry + lower) / 2) * (1 - 1 / leverage + mmr)
        frac = initial_fraction(entry, lower, upper, "long")

    return GridLiquidation(side, round(avg, 2), round(liq, 2), round(frac, 3), leverage)
