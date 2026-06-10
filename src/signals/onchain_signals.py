"""Senales de suelo de ciclo on-chain (reutilizan el dataclass Signal)."""
from __future__ import annotations

import pandas as pd

from src.signals.price_signals import Signal


def signal_mvrv_z(valuation: pd.DataFrame, floor: float = 0.5) -> Signal:
    """MVRV Z-Score. < floor => zona verde / capitulacion de valoracion."""
    if valuation.empty or "mvrv_z" not in valuation:
        return Signal("MVRV Z-Score", None, False, "sin datos")
    z = float(valuation["mvrv_z"].iloc[-1])
    return Signal("MVRV Z-Score", z, z < floor, f"MVRV Z = {z:.2f} (suelo < {floor})")


def signal_realized_price(valuation: pd.DataFrame, price: float, floor: float = 1.0) -> Signal:
    """Ratio precio/realized price. < floor (1.0) => precio bajo coste base agregado."""
    if valuation.empty or "realized_price" not in valuation:
        return Signal("Realized Price", None, False, "sin datos")
    rp = float(valuation["realized_price"].iloc[-1])
    ratio = price / rp
    return Signal("Realized Price", ratio, ratio < floor,
                  f"precio/realized = {ratio:.2f} (realized = {rp:,.0f}; suelo < {floor})")


def signal_hash_ribbons(hashrate: pd.Series) -> Signal:
    """Hash Ribbons: SMA30 < SMA60 del hashrate => capitulacion de mineros (estres tipico de suelo)."""
    if hashrate is None or len(hashrate) < 60:
        return Signal("Hash Ribbons", None, False, "sin datos")
    sma30 = hashrate.rolling(30).mean().iloc[-1]
    sma60 = hashrate.rolling(60).mean().iloc[-1]
    capitulation = bool(sma30 < sma60)
    detail = "capitulacion de mineros (SMA30 < SMA60)" if capitulation else "mineros estables (SMA30 >= SMA60)"
    return Signal("Hash Ribbons", float(sma30 - sma60), capitulation, detail)


def signal_puell(miners_revenue: pd.Series, floor: float = 0.5) -> Signal:
    """Puell Multiple = ingresos diarios / SMA365. < floor => suelo."""
    if miners_revenue is None or len(miners_revenue) < 365:
        return Signal("Puell Multiple", None, False, "sin datos")
    ma365 = miners_revenue.rolling(365).mean().iloc[-1]
    puell = float(miners_revenue.iloc[-1] / ma365)
    return Signal("Puell Multiple", puell, puell < floor, f"Puell = {puell:.2f} (suelo < {floor})")


def compute(valuation: pd.DataFrame, hashrate: pd.Series, miners_revenue: pd.Series,
            price: float, cfg: dict) -> list[Signal]:
    """Calcula todas las senales on-chain."""
    th = cfg["signals"]
    return [
        signal_mvrv_z(valuation, th["mvrv_z_floor"]),
        signal_realized_price(valuation, price, th["realized_price_ratio_floor"]),
        signal_hash_ribbons(hashrate),
        signal_puell(miners_revenue, th["puell_floor"]),
    ]
