"""Simulador de un grid de futuros sobre OHLCV horario.

Modela el grid como lo hace Pionex (verificado en su Help Center):
- Un grid LONG abre una POSICION INICIAL larga (inventario para vender en los niveles por
  encima del precio de entrada) y GANA con la tendencia alcista ademas de la rejilla. Un
  grid SHORT, simetrico, gana con la tendencia bajista.
- Un grid NEUTRAL no abre posicion inicial: compra (long) por debajo del precio de entrada
  y vende (short) por encima; su exposicion neta es ~0 y vive de la oscilacion.

Mecanica (inventario por nivel, close horario):
- held_long[j]=precio de compra del inventario que se vende al alcanzar levels[j].
- held_short[j]=precio de venta(short) del inventario que se recompra al alcanzar levels[j].
- realized acumula el PnL de cada operacion cerrada (incluye la captura direccional de la
  posicion inicial); al cierre se suma el PnL no realizado de lo que quede abierto.

Cierre: SL, TP (long/short), vuelta al equilibrio tras >=tp_rounds (neutral), o max_days.
Limitacion: usa el close 1h (no high/low intrabar) -> subestima algo las rondas.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class GridResult:
    pnl: float
    return_pct: float
    grid_profit: float        # PnL realizado (rejilla + captura direccional de la posicion inicial)
    trend_pnl: float          # PnL no realizado de la posicion abierta al cerrar
    rounds: int
    days: float
    exit_reason: str
    max_drawdown_pct: float
    buy_hold_pct: float


def _levels(lower: float, upper: float, n: int) -> list[float]:
    r = (upper / lower) ** (1.0 / n)
    return [lower * r ** i for i in range(n + 1)]


def simulate_grid(prices: pd.DataFrame, plan, entry_price: float, cfg: dict,
                  max_days: int = 60, tp_rounds: int = 8) -> GridResult:
    fee = cfg["fees"]["taker"]
    n = plan.grids
    levels = _levels(plan.lower, plan.upper, n)
    qty = (plan.investment * plan.leverage) / n / entry_price
    side = plan.bot_type

    held_long: dict[int, float] = {}   # j -> precio compra; se vende al alcanzar levels[j]
    held_short: dict[int, float] = {}  # j -> precio venta(short); se recompra al alcanzar levels[j]
    realized = 0.0
    rounds = 0

    # Posicion inicial direccional (captura la tendencia a favor dentro del rango)
    if side == "long":
        for j, lv in enumerate(levels):
            if lv > entry_price:
                held_long[j] = entry_price
                realized -= qty * entry_price * fee
    elif side == "short":
        for j, lv in enumerate(levels):
            if lv < entry_price:
                held_short[j] = entry_price
                realized -= qty * entry_price * fee

    def avg(d: dict, fallback: float) -> float:
        return sum(d.values()) / len(d) if d else fallback

    start = prices.index[0]
    last = entry_price
    final_price = entry_price
    days = 0.0
    equity_peak = 0.0
    max_dd = 0.0
    exit_reason = "timeout"
    sl, tp, be = plan.stop_loss, plan.take_profit, plan.break_even

    for ts, row in prices.iterrows():
        c = float(row["close"])
        days = (ts - start).total_seconds() / 86400.0

        if c > last:                                   # ---- subida ----
            for j in sorted(held_long):                # vender longs alcanzados
                if c >= levels[j]:
                    bp = held_long.pop(j)
                    realized += qty * (levels[j] - bp) - qty * levels[j] * fee
                    rounds += 1
            if side in ("short", "neutral"):           # abrir shorts arriba
                for k, lv in enumerate(levels):
                    if last < lv <= c and (side == "short" or lv > entry_price) and (k - 1) not in held_short and k - 1 >= 0:
                        held_short[k - 1] = lv
                        realized -= qty * lv * fee
        elif c < last:                                 # ---- bajada ----
            for j in sorted(held_short):               # recomprar shorts alcanzados
                if c <= levels[j]:
                    sp = held_short.pop(j)
                    realized += qty * (sp - levels[j]) - qty * levels[j] * fee
                    rounds += 1
            if side in ("long", "neutral"):            # abrir longs abajo
                for k, lv in enumerate(levels):
                    if c <= lv < last and (side == "long" or lv <= entry_price) and (k + 1) not in held_long and k + 1 <= n:
                        held_long[k + 1] = lv
                        realized -= qty * lv * fee
        last = c
        final_price = c

        unreal = (qty * len(held_long) * (c - avg(held_long, c))
                  - qty * len(held_short) * (c - avg(held_short, c)))
        equity = realized + unreal
        equity_peak = max(equity_peak, equity)
        max_dd = max(max_dd, equity_peak - equity)

        if side in ("long", "neutral") and sl is not None and c <= sl:
            exit_reason = "SL"; break
        if side == "short" and sl is not None and c >= sl:
            exit_reason = "SL"; break
        if side == "long" and tp is not None and c >= tp:
            exit_reason = "TP"; break
        if side == "short" and tp is not None and c <= tp:
            exit_reason = "TP"; break
        if side == "neutral" and be is not None and rounds >= tp_rounds and abs(c - be) <= be * 0.002:
            exit_reason = "equilibrio"; break
        if days >= max_days:
            exit_reason = "timeout"; break

    trend_pnl = (qty * len(held_long) * (final_price - avg(held_long, final_price))
                 - qty * len(held_short) * (final_price - avg(held_short, final_price)))
    pnl = realized + trend_pnl
    inv = plan.investment
    return GridResult(
        pnl=round(pnl, 2),
        return_pct=round(pnl / inv * 100, 2),
        grid_profit=round(realized, 2),
        trend_pnl=round(trend_pnl, 2),
        rounds=rounds,
        days=round(days, 1),
        exit_reason=exit_reason,
        max_drawdown_pct=round(max_dd / inv * 100, 2),
        buy_hold_pct=round((final_price / entry_price - 1.0) * 100, 2),
    )
