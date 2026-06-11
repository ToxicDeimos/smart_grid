#!/usr/bin/env python
"""Time-series momentum como senal direccional para grids de futuros.

Factor con evidencia academica (Moskowitz et al.; replicado en cripto): el retorno pasado a
N dias predice positivamente el retorno futuro. Aqui:
  - senal = retorno de BTC a N dias.  LONG si > 0, SHORT si < 0.  Grid a favor.
  - variante ALTA CONVICCION: solo operar cuando |momentum| esta en el 50% mas fuerte.
Horizontes 30/90/180. Validacion in-sample(<2024) / out-of-sample(>=2024).
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


def summarize(name, rows):
    if not rows:
        print(f"  {name:<30} sin senales")
        return
    allr = [r for r, _ in rows]
    ins = [r for r, y in rows if y < 2024]
    oos = [r for r, y in rows if y >= 2024]

    def st(xs):
        if not xs:
            return "-"
        w = sum(1 for x in xs if x > 0)
        return f"n={len(xs):<3} medio={statistics.mean(xs):+6.2f}%  rent={100 * w / len(xs):.0f}%"
    print(f"  {name:<30} GLOB {st(allr)} | in {st(ins)} | OUT {st(oos)}")


def main():
    cfg = load_config()
    cap = cfg["capital_usdt"]
    score = BottomScore(50.0, "x")
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    close = daily["close"]

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]

    print("\nTime-series momentum como senal direccional (BTC 2021-2026, 1h):\n")
    for N in (30, 90, 180):
        mom = close.pct_change(N)
        thr = mom.abs().median()
        any_rows, strong_rows = [], []
        for d in days:
            dd = daily.loc[:d]
            if len(dd) < 220 or pd.isna(mom.loc[d]):
                continue
            m = float(mom.loc[d])
            fut = hourly.loc[d:]
            if len(fut) < 24:
                continue
            c = float(dd["close"].iloc[-1])
            side = "long" if m > 0 else "short"
            ret = simulate_grid(fut, optimize(dd, BotDecision(side, "x"), score, cap, cfg), c, cfg).return_pct
            any_rows.append((ret, d.year))
            if abs(m) >= thr:
                strong_rows.append((ret, d.year))
        summarize(f"mom {N}d (cualquiera)", any_rows)
        summarize(f"mom {N}d (alta conviccion)", strong_rows)
        print()


if __name__ == "__main__":
    main()
