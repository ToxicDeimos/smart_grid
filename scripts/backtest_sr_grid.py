#!/usr/bin/env python
"""Estrategia: grid DIRECCIONAL ubicado en soportes/resistencias fuertes (diario).

- Detecta S/R fuertes (swing pivots + clustering + toques) hasta cada fecha.
- Si el precio esta en el TERCIO INFERIOR del rango [soporte, resistencia] -> grid LONG
  (apuesta rebote desde soporte). Rango del grid = [soporte, resistencia].
- Si esta en el TERCIO SUPERIOR -> grid SHORT (apuesta rechazo desde resistencia).
- Si esta en medio -> no se opera.

Simula con datos 1h intra-barra y separa in-sample(<2024) / out-of-sample(>=2024).
Parametros del detector fijados a priori. Sanity-check, no promesa.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.exchange import fetch_ohlcv  # noqa: E402
from src.grid.optimizer import GridPlan, _grids_for_range, _price_step, _round_to  # noqa: E402
from src.signals.levels import nearest_levels, support_resistance  # noqa: E402


def build_plan(side, lower, upper, cap, cfg, price) -> GridPlan:
    step = _price_step(price)
    lower, upper = _round_to(lower, step), _round_to(upper, step)
    grids = _grids_for_range(lower, upper, cfg["grid"]["min_net_pct_per_grid"], cfg["fees"]["taker"])
    lev = float(cfg["pionex"]["min_leverage"])
    sl_pct, tp_pct = cfg["grid"]["sl_pct"], cfg["grid"]["tp_pct"]
    if side == "long":
        sl, tp = _round_to(lower * (1 - sl_pct), step), _round_to(upper * (1 + tp_pct), step)
    else:
        sl, tp = _round_to(upper * (1 + sl_pct), step), _round_to(lower * (1 - tp_pct), step)
    return GridPlan(side, None, lower, upper, grids, lev, cap, sl, tp, 0.003)


def summarize(name, rows):
    if not rows:
        print(f"  {name:<18} sin senales")
        return
    allr = [r for r, _ in rows]
    ins = [r for r, y in rows if y < 2024]
    oos = [r for r, y in rows if y >= 2024]

    def st(xs):
        if not xs:
            return "-"
        w = sum(1 for x in xs if x > 0)
        return f"n={len(xs):<3} medio={statistics.mean(xs):+6.2f}%  rent={100 * w / len(xs):.0f}%"
    print(f"  {name:<18} GLOBAL {st(allr)}")
    print(f"  {'':<18}   in(<24)  {st(ins)}")
    print(f"  {'':<18}   OUT(>=24) {st(oos)}")


def main():
    cfg = load_config()
    cap = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]

    longs, shorts = [], []
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        c = float(dd["close"].iloc[-1])
        sup, res = support_resistance(dd, k=5, tol=0.025, min_touches=2, lookback=365)
        s, r = nearest_levels(c, sup, res)
        if not s or not r or r[0] <= s[0]:
            continue
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue
        pos = (c - s[0]) / (r[0] - s[0])     # posicion en el rango [0..1]
        yr = d.year
        if pos < 0.33:                        # cerca del soporte -> long
            ret = simulate_grid(fut, build_plan("long", s[0], r[0], cap, cfg, c), c, cfg).return_pct
            longs.append((ret, yr))
        elif pos > 0.67:                      # cerca de la resistencia -> short
            ret = simulate_grid(fut, build_plan("short", s[0], r[0], cap, cfg, c), c, cfg).return_pct
            shorts.append((ret, yr))

    print("\nGrid direccional en S/R fuertes (BTC 2021-2026, 1h):\n")
    summarize("LONG en soporte", longs)
    print()
    summarize("SHORT en resistencia", shorts)


if __name__ == "__main__":
    main()
