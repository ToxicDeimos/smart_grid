"""Simulador de un grid de futuros sobre OHLCV horario.

Modelo (aproximado pero defendible):
- Niveles geometricos entre lower y upper (grids+1 lineas).
- Rejilla compra-abajo / vende-arriba con inventario por nivel: al cruzar un nivel a la baja
  se compra qty_per_grid (abre inventario); al cruzar el nivel inmediatamente superior se
  vende ese inventario y se captura la ganancia de rejilla (spacing - fees) = 1 ronda.
- Posicion neta = inventario abierto; PnL no realizado = posicion * (precio - entrada media).
- Cierre: SL tocado, TP (long/short), vuelta al equilibrio tras >=tp_rounds (neutral), o max_days.

Supuestos / limitaciones (honestos):
- Usa el close horario para detectar cruces (no high/low intrabar): subestima algo las rondas.
- Modela una rejilla LONG; un grid neutral real cubre con shorts arriba, asi que el PnL de
  tendencia aqui es algo mas conservador (pesimista) que la realidad. Para 'short' el modelo
  es solo una aproximacion (se trata como la misma rejilla).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class GridResult:
    pnl: float                # PnL total en USDT
    return_pct: float         # PnL / inversion (%)
    grid_profit: float        # ganancia de rejilla
    trend_pnl: float          # PnL de tendencia (posicion neta al cerrar)
    rounds: int               # rondas de arbitraje completadas
    days: float               # dias que corrio
    exit_reason: str          # "SL" | "TP" | "equilibrio" | "timeout"
    max_drawdown_pct: float   # peor caida del equity (% de la inversion)
    buy_hold_pct: float       # retorno de comprar y mantener en el mismo periodo


def _levels(lower: float, upper: float, n: int) -> list[float]:
    r = (upper / lower) ** (1.0 / n)
    return [lower * r ** i for i in range(n + 1)]


def simulate_grid(prices: pd.DataFrame, plan, entry_price: float, cfg: dict,
                  max_days: int = 60, tp_rounds: int = 8) -> GridResult:
    """Simula `plan` sobre `prices` (OHLCV 1h, indice de fechas) desde entry_price."""
    fee = cfg["fees"]["taker"]
    n = plan.grids
    levels = _levels(plan.lower, plan.upper, n)
    qty = (plan.investment * plan.leverage) / n / entry_price  # BTC por grid (aprox)

    held: dict[int, float] = {}   # idx de nivel -> precio de compra (inventario abierto)
    position = 0.0
    cost = 0.0
    grid_profit = 0.0
    rounds = 0

    start = prices.index[0]
    last_close = entry_price
    final_price = entry_price
    days = 0.0
    equity_peak = 0.0
    max_dd = 0.0
    exit_reason = "timeout"
    side, sl, tp, be = plan.bot_type, plan.stop_loss, plan.take_profit, plan.break_even

    for ts, row in prices.iterrows():
        c = float(row["close"])
        days = (ts - start).total_seconds() / 86400.0

        if c < last_close:                                   # bajada: comprar
            for i, lv in enumerate(levels):
                if c <= lv < last_close and i not in held:
                    held[i] = lv
                    position += qty
                    cost += qty * lv
                    grid_profit -= qty * lv * fee
        elif c > last_close:                                 # subida: vender inventario
            for i in sorted(held):
                lv_sell = levels[i + 1] if i + 1 <= n else levels[i]
                if c >= lv_sell:
                    buy_price = held.pop(i)
                    position -= qty
                    cost -= qty * buy_price
                    grid_profit += qty * (lv_sell - buy_price) - qty * lv_sell * fee
                    rounds += 1
        last_close = c
        final_price = c

        avg = (cost / position) if position > 1e-12 else c
        equity = grid_profit + position * (c - avg)
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

    avg = (cost / position) if abs(position) > 1e-12 else final_price
    trend_pnl = position * (final_price - avg)
    pnl = grid_profit + trend_pnl
    inv = plan.investment
    return GridResult(
        pnl=round(pnl, 2),
        return_pct=round(pnl / inv * 100, 2),
        grid_profit=round(grid_profit, 2),
        trend_pnl=round(trend_pnl, 2),
        rounds=rounds,
        days=round(days, 1),
        exit_reason=exit_reason,
        max_drawdown_pct=round(max_dd / inv * 100, 2),
        buy_hold_pct=round((final_price / entry_price - 1.0) * 100, 2),
    )
