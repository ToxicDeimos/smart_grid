#!/usr/bin/env python
"""Walk-forward: valida la rentabilidad de las recomendaciones del sistema.

En N fechas historicas genera la recomendacion completa (score / regimen / optimizer con
datos SOLO hasta esa fecha) y simula el grid resultante con datos 1h del periodo siguiente.
Responde: ¿habrian sido rentables las recomendaciones?

ADVERTENCIA: el simulador es una aproximacion (ver grid_sim.py: rejilla long, close 1h).
Pocos regimenes de mercado en la muestra. Es un sanity-check de rentabilidad, no una promesa.
"""
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.backtest.grid_sim import simulate_grid  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.grid.bot_type import decide  # noqa: E402
from src.grid.optimizer import optimize  # noqa: E402
from src.regime.regime import detect  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402


def run() -> list:
    cfg = load_config()
    capital = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    val_full = onchain.get_valuation()
    hr_full = onchain.get_hashrate()
    mr_full = onchain.get_miners_revenue()

    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)
    dates = pd.date_range(start, end, freq="21D")

    results = []
    for d in dates:
        dd = daily.loc[:d]
        if len(dd) < 220:
            continue
        w, m = weekly(dd), monthly(dd)
        val = val_full.loc[:d] if len(val_full) else val_full
        hr = hr_full.loc[:d] if len(hr_full) else hr_full
        mr = mr_full.loc[:d] if len(mr_full) else mr_full
        score, _ = compute_all(dd, w, m, val, hr, mr, cfg)
        regime = detect(dd)
        decision = decide(regime, score)
        plan = optimize(dd, decision, score, capital, cfg)
        entry = float(dd["close"].iloc[-1])
        future = hourly.loc[d:]
        if len(future) < 24:
            continue
        res = simulate_grid(future, plan, entry, cfg, max_days=60, tp_rounds=8)
        results.append((d, decision.bot_type, regime.trend, res))
    return results


def _breakdown(title: str, results: list, key) -> None:
    groups = defaultdict(list)
    for row in results:
        groups[key(row)].append(row[3].return_pct)
    print(f"  --- por {title} ---")
    for g, xs in sorted(groups.items()):
        w = sum(1 for x in xs if x > 0)
        print(f"  {g:<10} n={len(xs):<3} rentables={w}/{len(xs)}   retorno medio={statistics.mean(xs):+.2f}%")


def report(results: list) -> None:
    if not results:
        print("Sin resultados.")
        return
    rets = [r.return_pct for _, _, _, r in results]
    bh = [r.buy_hold_pct for _, _, _, r in results]
    wins = [x for x in rets if x > 0]
    grid = [r.grid_profit for _, _, _, r in results]
    trend = [r.trend_pnl for _, _, _, r in results]

    print("=" * 72)
    print(f"  WALK-FORWARD DE RECOMENDACIONES DE GRID  -  {len(results)} simulaciones")
    print("=" * 72)
    print(f"  Rentables:         {len(wins)}/{len(results)} ({100 * len(wins) / len(results):.0f}%)")
    print(f"  Retorno medio:     {statistics.mean(rets):+.2f}%    mediana: {statistics.median(rets):+.2f}%")
    print(f"  Mejor / peor:      {max(rets):+.2f}% / {min(rets):+.2f}%")
    print(f"  Buy&hold medio:    {statistics.mean(bh):+.2f}%  (mismas ventanas, referencia)")
    print(f"  PnL rejilla medio: {statistics.mean(grid):+.2f} USDT   PnL tendencia medio: {statistics.mean(trend):+.2f} USDT")
    print("-" * 72)
    _breakdown("tipo de bot", results, key=lambda r: r[1])
    _breakdown("regimen", results, key=lambda r: r[2])
    print("-" * 72)
    reasons = defaultdict(int)
    for _, _, _, r in results:
        reasons[r.exit_reason] += 1
    print(f"  Cierres: {dict(reasons)}")
    print("=" * 72)
    print("  Aproximacion (rejilla long, close 1h). Pocos regimenes: sanity-check, no promesa.")


if __name__ == "__main__":
    report(run())
