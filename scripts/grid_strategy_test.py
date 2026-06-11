#!/usr/bin/env python
"""Experimento: ¿mejora el grid filtrando por direccion de la tendencia y/o con SL ajustado?

Compara, sobre las mismas ventanas historicas (BTC 2021-2026, 1h):
  1. BASELINE             - lo que recomienda el sistema.
  2. A FAVOR de tendencia - long si alcista, short si bajista, neutral si lateral.
  3. A FAVOR + SL ajustado- igual, con Stop Loss mas cercano (corta la cola).
  4. SESGO ALCISTA        - long si alcista, neutral resto (sin shorts; el drift de BTC los castiga).

ADVERTENCIA: 4 estrategias probadas -> cuidado con el overfitting. Sanity-check, no promesa.
"""
import copy
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.grid.bot_type import BotDecision, decide  # noqa: E402
from src.grid.optimizer import optimize  # noqa: E402
from src.regime.regime import detect  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402


def a_favor(regime) -> str:
    return {"alcista": "long", "bajista": "short"}.get(regime.trend, "neutral")


def sesgo_alcista(regime) -> str:
    return "long" if regime.trend == "alcista" else "neutral"


def summarize(name: str, rets: list) -> None:
    if not rets:
        print(f"  {name}: sin datos")
        return
    wins = sum(1 for x in rets if x > 0)
    print(f"  {name:<26} n={len(rets):<3} medio={statistics.mean(rets):+.2f}%  "
          f"mediana={statistics.median(rets):+.2f}%  rentables={wins}/{len(rets)} "
          f"({100 * wins / len(rets):.0f}%)  peor={min(rets):+.1f}%")


def main() -> None:
    cfg = load_config()
    cap = cfg["capital_usdt"]
    cfg_sl = copy.deepcopy(cfg)
    cfg_sl["grid"]["sl_pct"] = 0.025  # SL mas ajustado

    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    val = onchain.get_valuation()
    hr = onchain.get_hashrate()
    mr = onchain.get_miners_revenue()
    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)

    base, favor, favor_sl, alcista = [], [], [], []
    for d in pd.date_range(start, end, freq="14D"):
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        w, m = weekly(dd), monthly(dd)
        v = val.loc[:d] if len(val) else val
        h = hr.loc[:d] if len(hr) else hr
        mn = mr.loc[:d] if len(mr) else mr
        score, _ = compute_all(dd, w, m, v, h, mn, cfg)
        regime = detect(dd)
        entry = float(dd["close"].iloc[-1])
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue

        plan_b = optimize(dd, decide(regime, score), score, cap, cfg)
        base.append(simulate_grid(fut, plan_b, entry, cfg).return_pct)

        dec_f = BotDecision(a_favor(regime), "a favor de tendencia")
        favor.append(simulate_grid(fut, optimize(dd, dec_f, score, cap, cfg), entry, cfg).return_pct)
        favor_sl.append(simulate_grid(fut, optimize(dd, dec_f, score, cap, cfg_sl), entry, cfg_sl).return_pct)

        dec_a = BotDecision(sesgo_alcista(regime), "sesgo alcista")
        alcista.append(simulate_grid(fut, optimize(dd, dec_a, score, cap, cfg), entry, cfg).return_pct)

    print("\nComparativa de estrategias (BTC 2021-2026, 1h):\n")
    summarize("1. BASELINE (sistema)", base)
    summarize("2. A FAVOR de tendencia", favor)
    summarize("3. A FAVOR + SL 2.5%", favor_sl)
    summarize("4. SESGO ALCISTA (sin shorts)", alcista)
    print("\n  Buy&hold y baseline comparten ventanas. 4 estrategias -> ojo al overfitting.")


if __name__ == "__main__":
    main()
