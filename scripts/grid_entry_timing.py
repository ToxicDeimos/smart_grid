#!/usr/bin/env python
"""Experimento: timing de entrada para grids direccionales, con CONFLUENCIA y validacion OOS.

Senales de entrada (a favor de la tendencia de fondo, close vs EMA200):
  - any         : entrar en cualquier dia de la tendencia (sin filtro).
  - rsi         : solo RSI (long si RSI<45; short si RSI>55).
  - confluencia : pullback/rebote a la EMA50 con rechazo + RSI girando.
      long_conf : alcista + el low toca la EMA50 + cierra por encima (rechazo) + RSI subiendo.
      short_conf: bajista + el high toca la EMA50 + cierra por debajo (rechazo) + RSI bajando.

Reporta global y separa IN-SAMPLE (<2024) vs OUT-OF-SAMPLE (>=2024): si una regla solo
funciona in-sample, es overfitting. BTC 2021-2026, simulacion 1h intra-barra.
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


def summarize(name: str, rows: list) -> None:
    """rows: lista de (ret, year)."""
    if not rows:
        print(f"  {name:<22} sin senales")
        return
    allr = [r for r, _ in rows]
    ins = [r for r, y in rows if y < 2024]
    oos = [r for r, y in rows if y >= 2024]

    def stat(xs):
        if not xs:
            return "  -"
        w = sum(1 for x in xs if x > 0)
        return f"n={len(xs):<3} medio={statistics.mean(xs):+6.2f}%  rent={100 * w / len(xs):.0f}%"

    print(f"  {name:<22} GLOBAL {stat(allr)}")
    print(f"  {'':<22}   in-sample(<24)  {stat(ins)}")
    print(f"  {'':<22}   OUT-sample(>=24) {stat(oos)}")


def main() -> None:
    cfg = load_config()
    cap = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    score = BottomScore(50.0, "x")

    close = daily["close"]
    ema200 = close.ewm(span=200, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    rsi14 = rsi(close, 14)
    rsi_prev = rsi14.shift(1)

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)
    days = daily.index[(daily.index >= start) & (daily.index <= end)][::2]

    res = {k: [] for k in ("long_any", "long_rsi", "long_conf", "short_any", "short_rsi", "short_conf")}
    for d in days:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        c = float(dd["close"].iloc[-1])
        lo, hi = float(dd["low"].iloc[-1]), float(dd["high"].iloc[-1])
        e200, e50 = float(ema200.loc[d]), float(ema50.loc[d])
        r, rp = float(rsi14.loc[d]), float(rsi_prev.loc[d])
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue
        yr = d.year

        if c > e200:        # tendencia alcista -> long
            ret = simulate_grid(fut, optimize(dd, BotDecision("long", "x"), score, cap, cfg), c, cfg).return_pct
            res["long_any"].append((ret, yr))
            if r < 45:
                res["long_rsi"].append((ret, yr))
            if lo <= e50 and c > e50 and r > rp:        # pullback a EMA50 + rechazo + RSI girando
                res["long_conf"].append((ret, yr))
        elif c < e200:      # tendencia bajista -> short
            ret = simulate_grid(fut, optimize(dd, BotDecision("short", "x"), score, cap, cfg), c, cfg).return_pct
            res["short_any"].append((ret, yr))
            if r > 55:
                res["short_rsi"].append((ret, yr))
            if hi >= e50 and c < e50 and r < rp:        # rebote a EMA50 + rechazo + RSI girando
                res["short_conf"].append((ret, yr))

    print("\nTiming de entrada (BTC 2021-2026, 1h). Confluencia = pullback/rebote a EMA50.\n")
    for k in ("long_any", "long_rsi", "long_conf", "short_any", "short_rsi", "short_conf"):
        summarize(k, res[k])
        print()


if __name__ == "__main__":
    main()
