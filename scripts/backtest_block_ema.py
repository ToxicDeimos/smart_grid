#!/usr/bin/env python
"""Filtro de confluencia: operar SOLO donde un bloque coincide con la EMA200.

- Tendencia = pendiente de la EMA200 (sube -> long; baja -> short).
- Confluencia = el precio esta tocando la EMA200 (|precio-EMA200| <= 3%) Y hay un BLOQUE
  (zona de alta densidad de cierres) cerca de la EMA200.
- Se compara operar SIN filtro (a favor de la pendiente cualquier dia) vs operar SOLO en
  esos puntos de confluencia. Si la confluencia mejora la media/OOS, el filtro aporta valor.

Validacion in-sample(<2024) / out-of-sample(>=2024). Idea orientativa, no quirurgica.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.exchange import fetch_ohlcv  # noqa: E402
from src.grid.bot_type import BotDecision  # noqa: E402
from src.grid.optimizer import optimize  # noqa: E402
from src.signals.bottom_score import BottomScore  # noqa: E402
from src.signals.levels import block_near  # noqa: E402


def summarize(name, rows):
    if not rows:
        print(f"  {name:<32} sin senales")
        return
    allr = [r for r, _ in rows]
    ins = [r for r, y in rows if y < 2024]
    oos = [r for r, y in rows if y >= 2024]

    def st(xs):
        if not xs:
            return "-"
        w = sum(1 for x in xs if x > 0)
        return f"n={len(xs):<3} medio={statistics.mean(xs):+6.2f}%  rent={100 * w / len(xs):.0f}%"
    print(f"  {name:<32} GLOB {st(allr)} | in {st(ins)} | OUT {st(oos)}")


def main():
    cfg = load_config()
    cap = cfg["capital_usdt"]
    score = BottomScore(50.0, "x")
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    ema200 = daily["close"].ewm(span=200, adjust=False).mean()

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]

    no_filter, confl = [], []
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        i = dd.index.get_loc(d)
        if i < 30:
            continue
        ema_v, ema_prev = float(ema200.loc[d]), float(ema200.iloc[i - 30])
        side = "long" if ema_v > ema_prev else "short"
        c = float(dd["close"].iloc[-1])
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue
        ret = simulate_grid(fut, optimize(dd, BotDecision(side, "x"), score, cap, cfg), c, cfg).return_pct
        no_filter.append((ret, d.year))
        if abs(c - ema_v) / ema_v <= 0.03 and block_near(dd, ema_v):
            confl.append((ret, d.year))

    print("\nFiltro de confluencia bloque + EMA200 (BTC 2021-2026, 1h):\n")
    summarize("SIN filtro (pendiente EMA200)", no_filter)
    summarize("CON confluencia bloque+EMA200", confl)


if __name__ == "__main__":
    main()
