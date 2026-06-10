#!/usr/bin/env python
"""Sanity-check del score de suelo en fechas historicas conocidas.

Comprueba que el termometro marca ALTO en los suelos de ciclo (dic-2018, nov-2022)
y BAJO en un techo (nov-2021). Recalcula cada score usando solo datos hasta esa fecha.

ADVERTENCIA: N pequeno (3-4 ciclos). Es un sanity-check, NO una validacion estadistica
out-of-sample. Las senales MVRV/Realized se omiten (sin fuente historica sin key).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402

CASES = {
    "Suelo 2018-12-15": "2018-12-15",
    "Techo 2021-11-10": "2021-11-10",
    "Suelo 2022-11-21": "2022-11-21",
}


def _score_as_of(ts, daily, hr_full, mr_full, cfg):
    d = daily.loc[:ts]
    if len(d) < 220:
        return None, None, None
    w, m = weekly(d), monthly(d)
    hr = hr_full.loc[:ts] if len(hr_full) else hr_full
    mr = mr_full.loc[:ts] if len(mr_full) else mr_full
    score, signals = compute_all(d, w, m, pd.DataFrame(), hr, mr, cfg)
    return score, float(d["close"].iloc[-1]), [s.name for s in signals if s.in_floor_zone]


def main() -> None:
    cfg = load_config()
    daily = fetch_ohlcv(timeframe="1d")
    hr_full = onchain.get_hashrate()
    mr_full = onchain.get_miners_revenue()

    print("=" * 66)
    print("  BACKTEST SANITY-CHECK DEL SCORE DE SUELO")
    print("=" * 66)
    for label, date in CASES.items():
        ts = pd.Timestamp(date, tz="UTC")
        score, price, active = _score_as_of(ts, daily, hr_full, mr_full, cfg)
        if score is None:
            print(f"  {label}:  datos insuficientes")
            continue
        print(f"  {label}   BTC ${price:>9,.0f}   ->   score {score.score:>5.1f}/100   "
              f"({len(active)} senales: {', '.join(active) if active else '-'})")
    print("-" * 66)
    score, price, active = _score_as_of(daily.index[-1], daily, hr_full, mr_full, cfg)
    print(f"  Hoy {daily.index[-1].date()}   BTC ${price:>9,.0f}   ->   score {score.score:>5.1f}/100")
    print("=" * 66)
    print("  N pequeno (3-4 ciclos): sanity-check, NO validacion estadistica.")


if __name__ == "__main__":
    main()
