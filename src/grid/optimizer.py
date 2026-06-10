"""Optimizador de parametros de un grid de futuros.

A partir del OHLCV, el tipo de bot decidido y el score de suelo, calcula: rango
(limites inferior/superior), trigger de entrada, numero de grids, apalancamiento,
SL/TP y el precio de liquidacion, con avisos de riesgo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from src.grid.bot_type import BotDecision
from src.liquidation import GridLiquidation
from src.liquidation import estimate as estimate_liq
from src.signals.bottom_score import BottomScore


@dataclass
class GridPlan:
    bot_type: str
    entry_trigger: float | None      # None = activar al precio actual
    lower: float
    upper: float
    grids: int
    leverage: float
    investment: float
    stop_loss: float | None
    take_profit: float | None
    liquidation: GridLiquidation
    net_pct_per_grid: float
    warnings: list[str] = field(default_factory=list)
    rationale: str = ""


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _price_step(price: float) -> float:
    """Step de redondeo adaptado a la escala del precio (~3 cifras significativas).

    BTC (~$60k) -> 100 ; ETH (~$3k) -> 10 ; XRP (~$2.5) -> 0.01. Evita que los niveles
    de activos de bajo precio colapsen a 0 (que provocaba una division por cero).
    """
    if price <= 0:
        return 1.0
    return 10.0 ** (math.floor(math.log10(price)) - 2)


def _round_to(x: float, step: float) -> float:
    return round(x / step) * step


def _fmt(x: float) -> str:
    """Formato de precio legible adaptado a la escala (para los avisos)."""
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 1:
        return f"{x:,.2f}"
    return f"{x:,.4f}"


def _grids_for_range(lower: float, upper: float, net_pct: float, fee: float) -> int:
    """Numero de grids para ~net_pct neto por grid (espaciado geometrico)."""
    if lower <= 0 or upper <= lower:
        return 2
    spacing = net_pct + 2 * fee          # bruto = neto objetivo + fees de ida y vuelta
    n = math.log(upper / lower) / math.log(1 + spacing)
    return max(2, int(n))


def optimize(daily: pd.DataFrame, decision: BotDecision, bottom: BottomScore,
             capital: float, cfg: dict) -> GridPlan:
    price = float(daily["close"].iloc[-1])
    step = _price_step(price)
    atr = float(_atr(daily, cfg["grid"]["atr_period"]).iloc[-1])
    lookback = cfg["grid"]["swing_lookback"]
    swing_low = float(daily["low"].tail(lookback).min())
    swing_high = float(daily["high"].tail(lookback).max())
    fee = cfg["fees"]["taker"]
    lev = float(cfg["pionex"]["min_leverage"])
    mmr = cfg["pionex"]["maintenance_margin_rate"]
    net_target = cfg["grid"]["min_net_pct_per_grid"]
    ath = float(daily["close"].cummax().iloc[-1])

    side = decision.bot_type
    warnings: list[str] = []

    if side == "long":
        lower = _round_to(swing_low, step)
        upper = _round_to(max(swing_high, price + 2 * atr), step)
        if bottom.score >= 65:
            trigger = None                      # activar ya
            liq_entry = price
        else:
            trigger = _round_to(swing_low + 0.25 * (price - swing_low), step)  # esperar caida
            liq_entry = trigger
        stop_loss = _round_to(lower * 0.97, step)
        take_profit = upper
    elif side == "short":
        upper = _round_to(swing_high, step)
        lower = _round_to(min(swing_low, price - 2 * atr), step)
        trigger = _round_to(swing_high - 0.25 * (swing_high - price), step)
        liq_entry = trigger
        stop_loss = _round_to(upper * 1.03, step)
        take_profit = lower
    else:  # neutral
        lower = _round_to(price - 2 * atr, step)
        upper = _round_to(price + 2 * atr, step)
        trigger = None
        liq_entry = price
        stop_loss = None
        take_profit = None

    grids = _grids_for_range(lower, upper, net_target, fee)
    spacing_real = (upper / lower) ** (1 / grids) - 1
    net_pct = spacing_real - 2 * fee

    liq = estimate_liq(side, lower, upper, lev, entry=liq_entry, mmr=mmr)

    # Aviso clave: liquidacion dentro de la zona de suelo de bear historica (-65% a -85% del ATH).
    bear_hi, bear_lo = ath * 0.35, ath * 0.15
    if side in ("long", "neutral") and bear_lo <= liq.liq_price <= bear_hi:
        warnings.append(
            f"La liquidacion (${_fmt(liq.liq_price)}) cae en la zona de suelo de bear historica "
            f"(${_fmt(bear_lo)}-${_fmt(bear_hi)}): a {lev:.0f}x te sacaria cerca del fondo."
        )
    if lev <= cfg["pionex"]["min_leverage"]:
        warnings.append(
            f"Apalancamiento {lev:.0f}x (minimo de Pionex). La liquidacion esta a "
            f"~{abs(liq.liq_price / price - 1) * 100:.0f}% del precio actual."
        )
    if net_pct <= 0:
        warnings.append("Espaciado demasiado fino: la ganancia por grid no cubre las fees; reduce el nº de grids.")

    return GridPlan(
        bot_type=side,
        entry_trigger=trigger,
        lower=lower,
        upper=upper,
        grids=grids,
        leverage=lev,
        investment=capital,
        stop_loss=stop_loss,
        take_profit=take_profit,
        liquidation=liq,
        net_pct_per_grid=round(net_pct, 5),
        warnings=warnings,
        rationale=decision.rationale,
    )
