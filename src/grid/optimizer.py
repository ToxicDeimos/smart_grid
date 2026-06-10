"""Optimizador de parametros de un grid de futuros.

A partir del OHLCV, el tipo de bot decidido y el score de suelo, calcula: rango
(limites inferior/superior), trigger de entrada, numero de grids, apalancamiento,
Stop Loss, y Take Profit / precio de equilibrio, con avisos de riesgo.

Notas sobre Pionex:
- La liquidacion la calcula Pionex al crear el bot (depende del margen, incl. margen
  adicional, y de su modelo); aqui no se estima.
- En un grid NEUTRAL, el Take Profit NO es un precio sobre el rango: Pionex cierra al
  volver al precio de equilibrio (centro) mediante "rondas de arbitraje". Por eso para
  neutral se reporta el precio de equilibrio como objetivo de cierre, no un TP de precio.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from src.grid.bot_type import BotDecision
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
    take_profit: float | None        # long/short: precio objetivo. neutral: None
    net_pct_per_grid: float
    break_even: float | None = None  # neutral: precio de equilibrio / objetivo de cierre
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
    """Step de redondeo adaptado a la escala del precio (~3 cifras significativas)."""
    if price <= 0:
        return 1.0
    return 10.0 ** (math.floor(math.log10(price)) - 2)


def _round_to(x: float, step: float) -> float:
    return round(x / step) * step


def _fmt(x: float) -> str:
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 1:
        return f"{x:,.2f}"
    return f"{x:,.4f}"


def _grids_for_range(lower: float, upper: float, net_pct: float, fee: float) -> int:
    """Numero de grids para ~net_pct neto por grid (espaciado geometrico)."""
    if lower <= 0 or upper <= lower:
        return 2
    spacing = net_pct + 2 * fee
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
    net_target = cfg["grid"]["min_net_pct_per_grid"]
    sl_pct = cfg["grid"]["sl_pct"]
    tp_pct = cfg["grid"]["tp_pct"]

    side = decision.bot_type
    break_even: float | None = None
    warnings: list[str] = []

    if side == "long":
        lower = _round_to(swing_low, step)
        upper = _round_to(max(swing_high, price + 2 * atr), step)
        trigger = None if bottom.score >= 65 else _round_to(swing_low + 0.25 * (price - swing_low), step)
        stop_loss = _round_to(lower * (1 - sl_pct), step)
        take_profit = _round_to(upper * (1 + tp_pct), step)
    elif side == "short":
        upper = _round_to(swing_high, step)
        lower = _round_to(min(swing_low, price - 2 * atr), step)
        trigger = _round_to(swing_high - 0.25 * (swing_high - price), step)
        stop_loss = _round_to(upper * (1 + sl_pct), step)
        take_profit = _round_to(lower * (1 - tp_pct), step)
    else:  # neutral
        lower = _round_to(price - 2 * atr, step)
        upper = _round_to(price + 2 * atr, step)
        trigger = None
        stop_loss = _round_to(lower * (1 - sl_pct), step)
        take_profit = None                                   # el TP neutral no es de precio
        break_even = _round_to((lower + upper) / 2, step)     # cierre al volver al equilibrio
        warnings.append(
            f"Take Profit (neutral): en Pionex se configura por RONDAS de arbitraje, no por "
            f"precio. Cierra al volver al equilibrio (~${_fmt(break_even)}) sin arrastrar PnL "
            "de tendencia; mas rondas = mas ganancia acumulada pero mas tiempo expuesto."
        )

    grids = _grids_for_range(lower, upper, net_target, fee)
    spacing_real = (upper / lower) ** (1 / grids) - 1
    net_pct = spacing_real - 2 * fee

    if lev <= cfg["pionex"]["min_leverage"]:
        warnings.append(
            f"Apalancamiento {lev:.0f}x (minimo de Pionex). Revisa el precio de liquidacion "
            "que muestra Pionex al crear el bot (en neutral suele estar bastante lejos)."
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
        net_pct_per_grid=round(net_pct, 5),
        break_even=break_even,
        warnings=warnings,
        rationale=decision.rationale,
    )
