"""Senales de suelo de ciclo basadas en precio.

Cada funcion devuelve un Signal con: valor, si esta en "zona de suelo" y un detalle
legible. Trabajan sobre DataFrames OHLCV (indice de fechas UTC) ya descargados.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Signal:
    name: str
    value: float | None
    in_floor_zone: bool
    detail: str


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI con suavizado de Wilder."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def signal_200wma(weekly: pd.DataFrame, price: float) -> Signal:
    """Media de 200 semanas: precio en o por debajo => zona de suelo."""
    if len(weekly) < 200:
        return Signal("200WMA", None, False, f"datos insuficientes ({len(weekly)} semanas < 200)")
    wma = float(weekly["close"].rolling(200).mean().iloc[-1])
    ratio = price / wma
    return Signal("200WMA", wma, price <= wma, f"precio/200WMA = {ratio:.2f} (200WMA={wma:,.0f})")


def signal_mayer(daily: pd.DataFrame, price: float, floor: float = 0.8) -> Signal:
    """Mayer Multiple = precio / 200DMA. < floor => zona de suelo."""
    if len(daily) < 200:
        return Signal("Mayer Multiple", None, False, "datos insuficientes (<200 dias)")
    dma200 = float(daily["close"].rolling(200).mean().iloc[-1])
    mm = price / dma200
    return Signal("Mayer Multiple", mm, mm < floor, f"Mayer = {mm:.2f} (suelo < {floor})")


def signal_drawdown(daily: pd.DataFrame, price: float, floor_pct: float = -0.70) -> Signal:
    """Drawdown desde el maximo historico. <= floor_pct => zona de suelo."""
    ath = float(daily["close"].cummax().iloc[-1])
    dd = price / ath - 1
    return Signal("Drawdown ATH", dd, dd <= floor_pct,
                  f"{dd * 100:.1f}% desde ATH (ATH={ath:,.0f}; suelo <= {floor_pct * 100:.0f}%)")


def signal_rsi_monthly(monthly: pd.DataFrame, floor: float = 35) -> Signal:
    """RSI mensual. < floor => zona de suelo."""
    if len(monthly) < 15:
        return Signal("RSI mensual", None, False, "datos insuficientes")
    r = float(rsi(monthly["close"]).iloc[-1])
    return Signal("RSI mensual", r, r < floor, f"RSI(14) mensual = {r:.1f} (suelo < {floor})")


def signal_bmsb(weekly: pd.DataFrame, price: float) -> Signal:
    """Bull Market Support Band (20W SMA + 21W EMA). Precio por debajo => fase no-alcista."""
    if len(weekly) < 21:
        return Signal("Bull Market Support Band", None, False, "datos insuficientes")
    sma20 = float(weekly["close"].rolling(20).mean().iloc[-1])
    ema21 = float(weekly["close"].ewm(span=21, adjust=False).mean().iloc[-1])
    band_low, band_high = min(sma20, ema21), max(sma20, ema21)
    return Signal("Bull Market Support Band", band_low, price <= band_high,
                  f"precio={price:,.0f} vs banda [{band_low:,.0f} - {band_high:,.0f}]")


def compute(daily: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame,
            cfg: dict) -> list[Signal]:
    """Calcula todas las senales de precio a partir de los OHLCV y la config."""
    price = float(daily["close"].iloc[-1])
    th = cfg["signals"]
    return [
        signal_200wma(weekly, price),
        signal_mayer(daily, price, th["mayer_multiple_floor"]),
        signal_drawdown(daily, price, th["drawdown_floor_pct"]),
        signal_rsi_monthly(monthly, th["rsi_monthly_floor"]),
        signal_bmsb(weekly, price),
    ]
