#!/usr/bin/env python
"""Entrada por TRIGGER en retroceso (no inmediata) para grids direccionales.

Como se opera de verdad: no entrar al precio actual, sino poner una orden en un nivel clave
y esperar a que el precio retroceda hasta el.
  LONG : tendencia alcista (close>EMA200). Trigger = soporte fuerte por debajo. Se espera
         hasta `wait_days` a que el precio lo toque (low<=soporte). Si toca -> grid long
         desde ahi (mejor precio). Si no toca -> NO se opera.
  SHORT: tendencia bajista. Trigger = resistencia fuerte por encima; espera el rebote.

Compara INMEDIATA (entrar ya) vs TRIGGER (esperar el retroceso). Validacion OOS.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.exchange import fetch_ohlcv  # noqa: E402
from src.signals.levels import nearest_levels, support_resistance  # noqa: E402
from scripts.backtest_sr_grid import build_plan  # noqa: E402


def summarize(name, rows):
    if not rows:
        print(f"  {name:<26} sin senales")
        return
    allr = [r for r, _ in rows]
    ins = [r for r, y in rows if y < 2024]
    oos = [r for r, y in rows if y >= 2024]

    def st(xs):
        if not xs:
            return "-"
        w = sum(1 for x in xs if x > 0)
        return f"n={len(xs):<3} medio={statistics.mean(xs):+6.2f}%  rent={100 * w / len(xs):.0f}%"
    print(f"  {name:<26} GLOB {st(allr)} | in {st(ins)} | OUT {st(oos)}")


def main():
    cfg = load_config()
    cap = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    ema200 = daily["close"].ewm(span=200, adjust=False).mean()

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=90)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::3]
    wait_days = 30

    imm_long, trg_long, imm_short, trg_short, no_fill = [], [], [], [], 0
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        c = float(dd["close"].iloc[-1])
        e200 = float(ema200.loc[d])
        sup, res = support_resistance(dd, k=5, tol=0.025, min_touches=2, lookback=365)
        s, r = nearest_levels(c, sup, res)
        if not s or not r or r[0] <= s[0]:
            continue
        yr = d.year

        if c > e200:        # alcista -> long, trigger en el soporte
            trigger = s[0]
            window = hourly.loc[d:d + pd.Timedelta(days=wait_days)]
            # inmediata: entrar ya al precio actual
            fut_i = hourly.loc[d:]
            if len(fut_i) >= 24:
                imm_long.append((simulate_grid(fut_i, build_plan("long", s[0], r[0], cap, cfg, c), c, cfg).return_pct, yr))
            # trigger: esperar a que el low toque el soporte
            hit = window[window["low"] <= trigger]
            if len(hit):
                t0 = hit.index[0]
                fut_t = hourly.loc[t0:]
                if len(fut_t) >= 24:
                    trg_long.append((simulate_grid(fut_t, build_plan("long", s[0], r[0], cap, cfg, trigger), trigger, cfg).return_pct, yr))
            else:
                no_fill += 1
        elif c < e200:      # bajista -> short, trigger en la resistencia
            trigger = r[0]
            window = hourly.loc[d:d + pd.Timedelta(days=wait_days)]
            fut_i = hourly.loc[d:]
            if len(fut_i) >= 24:
                imm_short.append((simulate_grid(fut_i, build_plan("short", s[0], r[0], cap, cfg, c), c, cfg).return_pct, yr))
            hit = window[window["high"] >= trigger]
            if len(hit):
                t0 = hit.index[0]
                fut_t = hourly.loc[t0:]
                if len(fut_t) >= 24:
                    trg_short.append((simulate_grid(fut_t, build_plan("short", s[0], r[0], cap, cfg, trigger), trigger, cfg).return_pct, yr))
            else:
                no_fill += 1

    print("\nEntrada inmediata vs trigger en retroceso a S/R (BTC 2021-2026, 1h):\n")
    summarize("LONG inmediata", imm_long)
    summarize("LONG trigger en soporte", trg_long)
    print()
    summarize("SHORT inmediata", imm_short)
    summarize("SHORT trigger en resist.", trg_short)
    print(f"\n  Senales sin fill (el precio no retrocedio al nivel en {wait_days}d): {no_fill}")


if __name__ == "__main__":
    main()
