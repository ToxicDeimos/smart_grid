#!/usr/bin/env python
"""Experimento: ¿mejora un grid DIRECCIONAL con timing de entrada (retrocesos) en vez de
entrar en cualquier precio?

Metodo coherente con trading tendencial ("buy the dip / sell the rip"):
  LONG  -> tendencia alcista (close > EMA200) y entrar en RETROCESO (RSI diario bajo).
  SHORT -> tendencia bajista (close < EMA200) y entrar en REBOTE (RSI diario alto).
Compara contra entrar en CUALQUIER dia de esa tendencia (sin filtro de retroceso).

BTC 2021-2026, simulacion 1h intra-barra. Sanity-check, no promesa.
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
from src.signals.price_signals import rsi  # noqa: E402


def summarize(name: str, xs: list) -> None:
    if not xs:
        print(f"  {name:<34} sin senales")
        return
    wins = sum(1 for x in xs if x > 0)
    print(f"  {name:<34} n={len(xs):<3} medio={statistics.mean(xs):+.2f}%  "
          f"mediana={statistics.median(xs):+.2f}%  rentables={wins}/{len(xs)} ({100 * wins / len(xs):.0f}%)  "
          f"peor={min(xs):+.1f}%")


def main() -> None:
    cfg = load_config()
    cap = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    score = BottomScore(50.0, "x")   # el timing no depende del score; entry = precio actual

    close = daily["close"]
    ema200 = close.ewm(span=200, adjust=False).mean()
    rsi14 = rsi(close, 14)

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]

    long_any, long_dip, short_any, short_rip = [], [], [], []
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        c = float(dd["close"].iloc[-1])
        e200 = float(ema200.loc[d])
        r = float(rsi14.loc[d])
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue

        if c > e200:                                  # tendencia alcista -> long
            ret = simulate_grid(fut, optimize(dd, BotDecision("long", "x"), score, cap, cfg), c, cfg).return_pct
            long_any.append(ret)
            if r < 45:                                # retroceso
                long_dip.append(ret)
        elif c < e200:                                # tendencia bajista -> short
            ret = simulate_grid(fut, optimize(dd, BotDecision("short", "x"), score, cap, cfg), c, cfg).return_pct
            short_any.append(ret)
            if r > 55:                                # rebote
                short_rip.append(ret)

    print("\nTiming de entrada para grids direccionales (BTC 2021-2026, 1h):\n")
    summarize("LONG en cualquier precio (alcista)", long_any)
    summarize("LONG en retroceso (RSI<45)", long_dip)
    summarize("SHORT en cualquier precio (bajista)", short_any)
    summarize("SHORT en rebote (RSI>55)", short_rip)


if __name__ == "__main__":
    main()
