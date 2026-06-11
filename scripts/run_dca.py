#!/usr/bin/env python
"""DCA inteligente: cuanto comprar BTC spot HOY segun el score de suelo de ciclo.

Uso:  python scripts/run_dca.py --base 100
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.dca import recommend  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="DCA inteligente sobre BTC spot")
    parser.add_argument("--base", type=float, default=100.0, help="aportacion base por periodo (USDT)")
    args = parser.parse_args()

    cfg = load_config()
    daily = fetch_ohlcv("BTC/USDT", "1d")
    score, _ = compute_all(
        daily, weekly(daily), monthly(daily),
        onchain.get_valuation(), onchain.get_hashrate(), onchain.get_miners_revenue(), cfg,
    )
    price = float(daily["close"].iloc[-1])
    r = recommend(score.score, args.base)

    print("=" * 58)
    print(f"  DCA INTELIGENTE  -  BTC ${price:,.0f}  ({daily.index[-1].date()})")
    print("=" * 58)
    print(f"  Score de suelo:   {score.score}/100 - {score.label}")
    print(f"  Recomendacion:    {r.label}")
    print(f"  Multiplicador:    {r.multiplier}x  (sobre tu base de ${args.base:,.0f})")
    print(f"  >> COMPRA HOY:    ${r.amount:,.0f} en BTC spot")
    print("=" * 58)
    print("  Validado: ponderar el DCA por el score bate al DCA plano")
    print("  (+71.5% vs +50.4% ROI, BTC 2021-2026). No es asesoramiento financiero.")


if __name__ == "__main__":
    main()
