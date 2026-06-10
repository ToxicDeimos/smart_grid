#!/usr/bin/env python
"""Termometro de suelo de ciclo: muestra cada senal y el score de confluencia.

Uso:  python scripts/bottom_dashboard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402


def _bar(score: float, width: int = 24) -> str:
    filled = int(round(score / 100 * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def main() -> None:
    cfg = load_config()
    daily = fetch_ohlcv(timeframe="1d")
    w, m = weekly(daily), monthly(daily)
    valuation = onchain.get_valuation()
    hashrate = onchain.get_hashrate()
    miners_revenue = onchain.get_miners_revenue()

    score, signals = compute_all(daily, w, m, valuation, hashrate, miners_revenue, cfg)
    price = float(daily["close"].iloc[-1])

    print("=" * 64)
    print(f"  TERMOMETRO DE SUELO DE CICLO  -  BTC ${price:,.0f}  ({daily.index[-1].date()})")
    print("=" * 64)
    for s in signals:
        mark = "[X]" if s.in_floor_zone else "[ ]"
        print(f"  {mark} {s.name:<26} {s.detail}")
    print("-" * 64)
    print(f"  SCORE: {score.score:>5.1f}/100   {_bar(score.score)}")
    print(f"  {score.label}")
    print(f"  Senales en zona de suelo: {len(score.active)}/{len(signals) - len(score.missing)}")
    if score.missing:
        print(f"  (sin datos, excluidas: {', '.join(score.missing)})")
    print("=" * 64)
    print("  Recordatorio: N pequeno (3-4 ciclos). Marco de gestion de riesgo")
    print("  por valoracion extrema, NO un edge estadistico demostrado.")


if __name__ == "__main__":
    main()
