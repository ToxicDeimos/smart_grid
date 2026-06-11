#!/usr/bin/env python
"""Grid SPOT (sin apalancamiento) vs comprar y mantener.

El grid spot compra BTC en los niveles bajos y vende en los altos (long-only, leverage 1,
sin liquidacion ni SL forzado): captura la oscilacion (rejilla) MAS el drift alcista de BTC,
sin la cola que destruia el grid apalancado.

Mide, sobre ventanas de 90 dias (BTC 2021-2026, 1h intra-barra):
  1. grid spot SIEMPRE                vs buy&hold
  2. grid spot SOLO en zona de suelo  (drawdown > 40% desde el maximo de 365d) vs buy&hold
Retorno, % positivos, drawdown. Validacion in-sample(<2024) / out-of-sample(>=2024).
"""
import statistics
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.exchange import fetch_ohlcv  # noqa: E402
from src.grid.bot_type import BotDecision  # noqa: E402
from src.grid.optimizer import optimize  # noqa: E402
from src.signals.bottom_score import BottomScore  # noqa: E402


def summarize(name, rows):
    if not rows:
        print(f"  {name:<26} sin senales")
        return
    grid = [g for g, _, _ in rows]
    bh = [b for _, b, _ in rows]
    dd = [d for _, _, d in rows]
    pos = 100 * sum(1 for x in grid if x > 0) / len(grid)
    print(f"  {name:<26} n={len(rows):<3} grid={statistics.mean(grid):+6.2f}%  "
          f"buy&hold={statistics.mean(bh):+6.2f}%  grid_pos={pos:.0f}%  dd_medio={statistics.mean(dd):.1f}%")


def report(name, rows):
    ins = [(g, b, d) for g, b, d, y in rows if y < 2024]
    oos = [(g, b, d) for g, b, d, y in rows if y >= 2024]
    allr = [(g, b, d) for g, b, d, y in rows]
    summarize(f"{name} GLOBAL", allr)
    summarize(f"{name} in-sample", ins)
    summarize(f"{name} OUT-sample", oos)


def main():
    cfg = load_config()
    cap = cfg["capital_usdt"]
    score = BottomScore(50.0, "x")
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    roll_max = daily["close"].rolling(365, min_periods=60).max()

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=90)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]

    always, dip = [], []
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        c = float(dd["close"].iloc[-1])
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue
        base = optimize(dd, BotDecision("long", "x"), score, cap, cfg)
        plan = replace(base, leverage=1.0, stop_loss=None, take_profit=None)  # SPOT: 1x, sin SL
        res = simulate_grid(fut, plan, c, cfg, max_days=90)
        row = (res.return_pct, res.buy_hold_pct, res.max_drawdown_pct, d.year)
        always.append(row)
        dd_from_max = (c / float(roll_max.loc[d]) - 1) * 100 if not pd.isna(roll_max.loc[d]) else 0
        if dd_from_max <= -40:                                  # zona de suelo
            dip.append(row)

    print("\nGRID SPOT (1x) vs buy&hold — BTC 2021-2026, ventanas de 90d:\n")
    report("Spot SIEMPRE", always)
    print()
    report("Spot en zona de suelo", dip)


if __name__ == "__main__":
    main()
