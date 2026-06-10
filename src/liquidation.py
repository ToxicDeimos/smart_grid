"""Calculo del precio de liquidacion de un futures grid (long / short / neutral).

Usa el modelo derivado durante el diseno: la posicion inicial abierta al activar el
grid es la fraccion del rango que queda en la direccion de las ordenes de salida, y la
liquidacion se estima con el precio medio de entrada cuando el grid esta lleno.

- long  : riesgo a la BAJA (el precio cae hasta 'lower' con la posicion larga abierta).
- short : riesgo al ALZA (el precio sube hasta 'upper').
- neutral: riesgo BILATERAL — longs por debajo (liquidacion a la baja) y shorts por
  encima (liquidacion al alza). Al estar parcialmente cubierto, su riesgo direccional
  real es MENOR que el de un grid puro; los valores aqui son una referencia conservadora.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GridLiquidation:
    side: str
    avg_entry: float
    liq_price: float                   # liquidacion principal: caida (long/neutral) o subida (short)
    initial_fraction: float            # fraccion del nocional abierta al activar el grid
    leverage: float
    direction: str = "down"            # "down" (long), "up" (short), "both" (neutral)
    liq_price_up: float | None = None  # solo neutral: liquidacion al alza (lado short)


def initial_fraction(entry: float, lower: float, upper: float, side: str = "long") -> float:
    """Fraccion del nocional que se abre como posicion inicial al activar el grid."""
    span = upper - lower
    if span <= 0:
        return 1.0
    frac = (upper - entry) / span if side == "long" else (entry - lower) / span
    return max(0.0, min(1.0, frac))


def estimate(side: str, lower: float, upper: float, leverage: float,
             entry: float | None = None, mmr: float = 0.005) -> GridLiquidation:
    """Estima la liquidacion del grid cuando esta completamente desplegado (peor caso)."""
    if side == "long":
        entry = entry if entry is not None else upper
        avg = (entry + lower) / 2
        liq = avg * (1 - 1 / leverage + mmr)
        frac = initial_fraction(entry, lower, upper, "long")
        return GridLiquidation("long", round(avg, 2), round(liq, 2), round(frac, 3),
                               leverage, "down", None)

    if side == "short":
        entry = entry if entry is not None else lower
        avg = (entry + upper) / 2
        liq = avg * (1 + 1 / leverage - mmr)
        frac = initial_fraction(entry, lower, upper, "short")
        return GridLiquidation("short", round(avg, 2), round(liq, 2), round(frac, 3),
                               leverage, "up", None)

    # neutral: longs por debajo del centro, shorts por encima -> riesgo en ambos extremos
    entry = entry if entry is not None else (upper + lower) / 2
    avg_long = (entry + lower) / 2
    avg_short = (entry + upper) / 2
    liq_down = avg_long * (1 - 1 / leverage + mmr)
    liq_up = avg_short * (1 + 1 / leverage - mmr)
    frac = initial_fraction(entry, lower, upper, "long")
    return GridLiquidation("neutral", round(entry, 2), round(liq_down, 2), round(frac, 3),
                           leverage, "both", round(liq_up, 2))
