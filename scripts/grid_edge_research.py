#!/usr/bin/env python
"""Investigacion: ¿que condiciones del mercado predicen un grid rentable?

Para cada fecha historica registra el estado del mercado al abrir el grid (eficiencia/ruido
de Kaufman, ADX, volatilidad 30d, ATR%) y el resultado del grid simulado. Luego analiza,
por terciles de cada metrica, el retorno medio -> candidato a filtro de niveles favorables.
"""
import statistics
import sys
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


def ker(close: pd.Series, n: int = 30):
    """Kaufman Efficiency Ratio: |cambio neto| / suma de movimientos. Bajo = lateral/ruidoso."""
    if len(close) <= n:
        return None
    change = abs(close.iloc[-1] - close.iloc[-1 - n])
    vol = close.diff().abs().tail(n).sum()
    return float(change / vol) if vol > 0 else 0.0


def atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    return float(atr / c.iloc[-1] * 100)


def run() -> list:
    cfg = load_config()
    cap = cfg["capital_usdt"]
    daily = fetch_ohlcv("BTC/USDT", "1d")
    hourly = fetch_ohlcv("BTC/USDT", "1h", since="2021-01-01")
    val = onchain.get_valuation()
    hr = onchain.get_hashrate()
    mr = onchain.get_miners_revenue()
    start = pd.Timestamp("2021-06-01", tz="UTC")
    end = daily.index[-1] - pd.Timedelta(days=60)

    rows = []
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
        decision = decide(regime, score)
        plan = optimize(dd, decision, score, cap, cfg)
        entry = float(dd["close"].iloc[-1])
        fut = hourly.loc[d:]
        if len(fut) < 24:
            continue
        res = simulate_grid(fut, plan, entry, cfg, max_days=60, tp_rounds=8)
        rows.append({
            "ret": res.return_pct,
            "ker": ker(dd["close"], 30),
            "adx": regime.adx,
            "vol30": float(dd["close"].pct_change().tail(30).std() * 100),
            "atr_pct": atr_pct(dd),
        })
    return rows


def terciles(rows: list, metric: str) -> None:
    vals = sorted((r[metric], r["ret"]) for r in rows if r[metric] is not None)
    n = len(vals)
    t = n // 3
    groups = {"bajo ": vals[:t], "medio": vals[t:2 * t], "alto ": vals[2 * t:]}
    print(f"  --- {metric} ---")
    for g, xs in groups.items():
        rets = [r for _, r in xs]
        if rets:
            wins = sum(1 for r in rets if r > 0)
            print(f"  {g} [{xs[0][0]:.2f}..{xs[-1][0]:.2f}]  n={len(rets):<3} "
                  f"retorno medio={statistics.mean(rets):+.1f}%  rentables={wins}/{len(rets)}")


def main() -> None:
    rows = run()
    print(f"\n{len(rows)} grids simulados. Retorno medio segun cada condicion al abrir:\n")
    for metric in ["ker", "adx", "vol30", "atr_pct"]:
        terciles(rows, metric)
        print()


if __name__ == "__main__":
    main()
