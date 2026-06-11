"""Simulador de un grid de futuros sobre OHLCV.

Modela el grid como Pionex (verificado en su Help Center):
- Un grid LONG abre POSICION INICIAL larga (inventario para vender en los niveles por encima
  del precio de entrada) y GANA con la tendencia alcista ademas de la rejilla. SHORT, simetrico.
- Un grid NEUTRAL no abre posicion inicial: compra (long) por debajo y vende (short) por encima.

Resolucion: cada barra se recorre por su rango INTRA-BARRA usando high/low (no solo el close),
asi se cuentan las oscilaciones que un grid real captura. Convencion del recorrido: si la barra
cierra al alza -> low->high->close; si cierra a la baja -> high->low->close. (El close-only
infra-cuenta las rondas; el rango intra-barra es el limite superior razonable.)

Cierres (SL / TP / equilibrio) se evaluan intra-barra con high/low. Limitacion: el orden exacto
del recorrido intra-barra es una aproximacion.
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

    held_long: dict[int, float] = {}
    held_short: dict[int, float] = {}
    st = {"realized": 0.0, "rounds": 0, "last": entry_price}

    if side == "long":
        for j, lv in enumerate(levels):
            if lv > entry_price:
                held_long[j] = entry_price
                st["realized"] -= qty * entry_price * fee
    elif side == "short":
        for j, lv in enumerate(levels):
            if lv < entry_price:
                held_short[j] = entry_price
                st["realized"] -= qty * entry_price * fee

    def avg(d: dict, fb: float) -> float:
        return sum(d.values()) / len(d) if d else fb

    def move(c: float) -> None:
        last = st["last"]
        if c > last:                                   # subida
            for j in sorted(held_long):
                if c >= levels[j]:
                    bp = held_long.pop(j)
                    st["realized"] += qty * (levels[j] - bp) - qty * levels[j] * fee
                    st["rounds"] += 1
            if side in ("short", "neutral"):
                for k, lv in enumerate(levels):
                    if last < lv <= c and (side == "short" or lv > entry_price) and (k - 1) not in held_short and k - 1 >= 0:
                        held_short[k - 1] = lv
                        st["realized"] -= qty * lv * fee
        elif c < last:                                 # bajada
            for j in sorted(held_short):
                if c <= levels[j]:
                    sp = held_short.pop(j)
                    st["realized"] += qty * (sp - levels[j]) - qty * levels[j] * fee
                    st["rounds"] += 1
            if side in ("long", "neutral"):
                for k, lv in enumerate(levels):
                    if c <= lv < last and (side == "long" or lv <= entry_price) and (k + 1) not in held_long and k + 1 <= n:
                        held_long[k + 1] = lv
                        st["realized"] -= qty * lv * fee
        st["last"] = c

    start = prices.index[0]
    final_price = entry_price
    days = 0.0
    equity_peak = 0.0
    max_dd = 0.0
    exit_reason = "timeout"
    sl, tp, be = plan.stop_loss, plan.take_profit, plan.break_even
    closed = False

    for ts, row in prices.iterrows():
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        days = (ts - start).total_seconds() / 86400.0
        for px in ([l, h, c] if c >= o else [h, l, c]):
            move(px)
        final_price = c

        unreal = (qty * len(held_long) * (c - avg(held_long, c))
                  - qty * len(held_short) * (c - avg(held_short, c)))
        equity = st["realized"] + unreal
        equity_peak = max(equity_peak, equity)
        max_dd = max(max_dd, equity_peak - equity)

        if side in ("long", "neutral") and sl is not None and l <= sl:
            final_price = sl; exit_reason = "SL"; closed = True
        elif side == "short" and sl is not None and h >= sl:
            final_price = sl; exit_reason = "SL"; closed = True
        elif side == "long" and tp is not None and h >= tp:
            final_price = tp; exit_reason = "TP"; closed = True
        elif side == "short" and tp is not None and l <= tp:
            final_price = tp; exit_reason = "TP"; closed = True
        elif side == "neutral" and be is not None and st["rounds"] >= tp_rounds and l <= be <= h:
            final_price = be; exit_reason = "equilibrio"; closed = True
        elif days >= max_days:
            exit_reason = "timeout"; closed = True
        if closed:
            break

    trend_pnl = (qty * len(held_long) * (final_price - avg(held_long, final_price))
                 - qty * len(held_short) * (final_price - avg(held_short, final_price)))
    pnl = st["realized"] + trend_pnl
    inv = plan.investment
    return GridResult(
        pnl=round(pnl, 2),
        return_pct=round(pnl / inv * 100, 2),
        grid_profit=round(st["realized"], 2),
        trend_pnl=round(trend_pnl, 2),
        rounds=st["rounds"],
        days=round(days, 1),
        exit_reason=exit_reason,
        max_drawdown_pct=round(max_dd / inv * 100, 2),
        buy_hold_pct=round((final_price / entry_price - 1.0) * 100, 2),
    )
