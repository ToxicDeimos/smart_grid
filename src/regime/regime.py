"""Deteccion de regimen de mercado: tendencia (alcista/bajista) vs rango lateral.

Insumo para decidir el tipo de bot de grid. Usa EMAs (50/200) para la direccion
y el ADX para distinguir tendencia de rango.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Regime:
    trend: str       # "alcista" | "bajista" | "lateral"
    adx: float
    detail: str


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index (suavizado de Wilder)."""
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def detect(daily: pd.DataFrame, adx_threshold: float = 20.0) -> Regime:
    """Clasifica el regimen actual a partir del OHLCV diario."""
    close = daily["close"]
    price = float(close.iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
    a = float(adx(daily).iloc[-1])

    if a < adx_threshold:
        trend = "lateral"
    elif price > ema50 > ema200:
        trend = "alcista"
    elif price < ema50 < ema200:
        trend = "bajista"
    else:
        trend = "alcista" if price > ema200 else "bajista"  # transicion

    detail = f"ADX={a:.1f} | precio={price:,.0f} EMA50={ema50:,.0f} EMA200={ema200:,.0f}"
    return Regime(trend, round(a, 1), detail)
