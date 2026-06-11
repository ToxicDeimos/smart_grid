"""Deteccion de soportes y resistencias fuertes (swing pivots + clustering + toques).

Metodo estandar (objetivo, no dependiente de la escala):
1. Pivots: un swing high es un maximo en una ventana de +-k velas; swing low, un minimo.
2. Clustering: se agrupan pivots cercanos (dentro de una tolerancia %) en una zona.
3. Fuerza: numero de pivots (toques) que forman la zona. Fuerte = >= min_touches.

Parametros fijados a priori (no tuneados al resultado) para no sobreajustar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def block_near(daily: pd.DataFrame, level: float, lookback: int = 365,
               bins: int = 40, tol: float = 0.03, density_q: float = 0.70) -> bool:
    """¿Hay un BLOQUE (zona de alta densidad de cierres = zona de valor) cerca de `level`?

    Construye un perfil de cuantas velas cerraron en cada banda de precio en la ventana;
    una banda con densidad alta (>= cuantil density_q) y dentro de tol% de `level` es una
    confluencia bloque-nivel.
    """
    win = daily.tail(lookback)["close"].to_numpy()
    if len(win) < 30:
        return False
    lo, hi = float(win.min()), float(win.max())
    if hi <= lo:
        return False
    hist, edges = np.histogram(win, bins=bins, range=(lo, hi))
    nz = hist[hist > 0]
    if nz.size == 0:
        return False
    thr = np.quantile(nz, density_q)
    for i, count in enumerate(hist):
        center = (edges[i] + edges[i + 1]) / 2
        if count >= thr and abs(center - level) / level <= tol:
            return True
    return False


def pivots(df: pd.DataFrame, k: int = 5) -> tuple[list[float], list[float]]:
    """Devuelve (swing_highs, swing_lows): extremos locales en ventana de +-k velas."""
    highs, lows = df["high"].to_numpy(), df["low"].to_numpy()
    sh, sl = [], []
    for i in range(k, len(df) - k):
        if highs[i] == highs[i - k:i + k + 1].max():
            sh.append(float(highs[i]))
        if lows[i] == lows[i - k:i + k + 1].min():
            sl.append(float(lows[i]))
    return sh, sl


def cluster(levels: list[float], tol: float = 0.025) -> list[tuple[float, int]]:
    """Agrupa niveles dentro de tol% en zonas. Devuelve (nivel_medio, n_toques)."""
    if not levels:
        return []
    levels = sorted(levels)
    out, cur = [], [levels[0]]
    for lv in levels[1:]:
        if (lv - cur[-1]) / cur[-1] <= tol:
            cur.append(lv)
        else:
            out.append((sum(cur) / len(cur), len(cur)))
            cur = [lv]
    out.append((sum(cur) / len(cur), len(cur)))
    return out


def support_resistance(daily: pd.DataFrame, k: int = 5, tol: float = 0.025,
                       min_touches: int = 2, lookback: int = 365
                       ) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
    """Soportes y resistencias fuertes (>= min_touches) en las ultimas `lookback` velas."""
    df = daily.tail(lookback)
    sh, sl = pivots(df, k)
    res = [(lv, n) for lv, n in cluster(sh, tol) if n >= min_touches]
    sup = [(lv, n) for lv, n in cluster(sl, tol) if n >= min_touches]
    return sup, res


def nearest_levels(price: float, sup: list[tuple[float, int]], res: list[tuple[float, int]]
                   ) -> tuple[tuple[float, int] | None, tuple[float, int] | None]:
    """Soporte fuerte mas cercano por debajo y resistencia fuerte mas cercana por encima."""
    below = [s for s in sup if s[0] < price]
    above = [r for r in res if r[0] > price]
    support = max(below, key=lambda x: x[0]) if below else None
    resistance = min(above, key=lambda x: x[0]) if above else None
    return support, resistance
