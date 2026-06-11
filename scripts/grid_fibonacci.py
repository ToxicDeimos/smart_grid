#!/usr/bin/env python
"""Retroceso de Fibonacci (diario) como punto de entrada para grids direccionales.

- Impulso = minimo y maximo de los ultimos 90 dias. Si el maximo es mas reciente -> impulso
  alcista (se espera retroceso a la baja -> LONG). Si el minimo es mas reciente -> bajista (SHORT).
- Niveles Fib del retroceso: 0.382 / 0.5 / 0.618. Se pone un TRIGGER en el nivel y se espera
  (wait_days) a que el precio retroceda y lo toque. Si toca -> grid a favor del impulso, rango
  [fib, maximo] (long) o [minimo, fib] (short). Si no toca -> no se opera.

Validacion in-sample(<2024) / out-of-sample(>=2024) por nivel Fib.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.exchange import fetch_ohlcv  # noqa: E402
from scripts.backtest_sr_grid import build_plan  # noqa: E402


def summarize(name, rows):
    if not rows:
        print(f"  {name:<22} sin senales")
        return
    allr = [r for r, _ in rows]
    ins = [r for r, y in rows if y < 2024]
    oos = [r for r, y in rows if y >= 2024]

    def st(xs):
        if not xs:
            return "-"
        w = sum(1 for x in xs if x > 0)
        return f"n={len(xs):<3} medio={statistics.mean(xs):+6.2f}%  rent={100 * w / len(xs):.0f}%"
    print(f"  {name:<22} GLOB {st(allr)} | in {st(ins)} | OUT {st(oos)}")


def main():
    cfg = load_config()
    cap = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=90)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]
    wait_days, lookback = 30, 90

    res = {0.382: [], 0.5: [], 0.618: []}
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        win = dd.tail(lookback)
        lo, hi = float(win["low"].min()), float(win["high"].max())
        lo_idx, hi_idx = win["low"].idxmin(), win["high"].idxmax()
        if hi <= lo:
            continue
        c = float(dd["close"].iloc[-1])
        wh = hourly.loc[d:d + pd.Timedelta(days=wait_days)]
        up = hi_idx > lo_idx                       # impulso alcista -> long en retroceso
        for ratio in res:
            if up:
                fib = hi - (hi - lo) * ratio
                if fib >= c:
                    continue
                hit = wh[wh["low"] <= fib]
                if len(hit):
                    fut = hourly.loc[hit.index[0]:]
                    if len(fut) >= 24:
                        ret = simulate_grid(fut, build_plan("long", fib, hi, cap, cfg, fib), fib, cfg).return_pct
                        res[ratio].append((ret, d.year))
            else:                                   # impulso bajista -> short en rebote
                fib = lo + (hi - lo) * ratio
                if fib <= c:
                    continue
                hit = wh[wh["high"] >= fib]
                if len(hit):
                    fut = hourly.loc[hit.index[0]:]
                    if len(fut) >= 24:
                        ret = simulate_grid(fut, build_plan("short", lo, fib, cap, cfg, fib), fib, cfg).return_pct
                        res[ratio].append((ret, d.year))

    print("\nGrid con entrada en retroceso de Fibonacci (BTC 2021-2026, 1h):\n")
    for ratio in (0.382, 0.5, 0.618):
        summarize(f"Fib {ratio}", res[ratio])


if __name__ == "__main__":
    main()
