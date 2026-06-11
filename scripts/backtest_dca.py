#!/usr/bin/env python
"""DCA inteligente (ponderado por el score de suelo) vs DCA plano vs lump sum.

Compra BTC spot cada semana (2021-2026):
  - PLANO    : cantidad fija cada semana.
  - INTELIGENTE: cantidad x multiplicador del score de suelo (mas barato/score alto -> compra mas).
  - LUMP SUM : todo el capital al inicio (referencia).

Metricas: precio medio de compra (mas bajo = mejor) y ROI al precio final. Si el inteligente
logra mejor precio medio y ROI que el plano, sobreponderar los suelos aporta valor.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402


def mult(score: float) -> float:
    """Multiplicador de compra: 1x (score 0) -> 3x (score 100)."""
    return 1.0 + 2.0 * (score / 100.0)


def main():
    cfg = load_config()
    daily = fetch_ohlcv("BTC/USDT", "1d")
    val = onchain.get_valuation()
    hr = onchain.get_hashrate()
    mr = onchain.get_miners_revenue()

    weeks = pd.date_range(pd.Timestamp("2021-01-04", tz="UTC"), daily.index[-1], freq="7D")
    base = 100.0  # USDT por semana en el plano
    final_price = float(daily["close"].iloc[-1])

    plano = {"inv": 0.0, "btc": 0.0}
    smart = {"inv": 0.0, "btc": 0.0}
    scores = []

    for w in weeks:
        dd = daily.loc[:w]
        if len(dd) < 220:
            continue
        price = float(dd["close"].iloc[-1])
        s, _ = compute_all(dd, weekly(dd), monthly(dd),
                           val.loc[:w] if len(val) else val,
                           hr.loc[:w] if len(hr) else hr,
                           mr.loc[:w] if len(mr) else mr, cfg)
        scores.append(s.score)
        plano["inv"] += base
        plano["btc"] += base / price
        inv = base * mult(s.score)
        smart["inv"] += inv
        smart["btc"] += inv / price

    def stats(d):
        avg_price = d["inv"] / d["btc"]
        value = d["btc"] * final_price
        roi = value / d["inv"] - 1
        return avg_price, roi, value, d["inv"]

    # lump sum: todo el capital del plano invertido en la primera semana
    first_price = float(daily.loc[:weeks[0]]["close"].iloc[-1]) if len(daily.loc[:weeks[0]]) else final_price
    lump_btc = plano["inv"] / first_price
    lump_roi = (lump_btc * final_price) / plano["inv"] - 1

    print(f"\nDCA semanal BTC 2021-2026 (precio final ${final_price:,.0f}). Score medio: {sum(scores)/len(scores):.1f}\n")
    for name, d in (("DCA PLANO", plano), ("DCA INTELIGENTE", smart)):
        ap, roi, val_, inv_ = stats(d)
        print(f"  {name:<16} invertido=${inv_:,.0f}  precio_medio=${ap:,.0f}  valor=${val_:,.0f}  ROI={roi*100:+.1f}%")
    print(f"  {'LUMP SUM':<16} (al inicio)                        ROI={lump_roi*100:+.1f}%")
    print(f"\n  Mejora del inteligente sobre el plano: precio medio "
          f"{(smart['inv']/smart['btc'])/(plano['inv']/plano['btc'])*100-100:+.1f}%, "
          f"ROI {(stats(smart)[1]-stats(plano)[1])*100:+.1f} pts")


if __name__ == "__main__":
    main()
