#!/usr/bin/env python
"""Recomendacion completa de bot de grid de futuros.

Uso:
  python scripts/run_recommendation.py --capital 2000 --symbol BTC/USDT
  python scripts/run_recommendation.py --json
  python scripts/run_recommendation.py --markdown
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import report  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.grid.bot_type import decide  # noqa: E402
from src.grid.optimizer import optimize  # noqa: E402
from src.regime.regime import detect  # noqa: E402
from src.signals.bottom_score import compute_all, compute_alt  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Recomendacion de grid de futuros (BTC / Pionex)")
    parser.add_argument("--capital", type=float, default=None, help="capital en USDT")
    parser.add_argument("--symbol", default=None, help="par de analisis (def: config)")
    parser.add_argument("--json", action="store_true", help="salida en JSON")
    parser.add_argument("--markdown", action="store_true", help="salida en markdown")
    args = parser.parse_args()

    cfg = load_config()
    capital = args.capital if args.capital is not None else cfg["capital_usdt"]
    symbol = args.symbol or cfg["symbol"]
    is_btc = symbol.split("/")[0].upper() in ("BTC", "XBT")

    daily = fetch_ohlcv(symbol=symbol, timeframe="1d")
    w, m = weekly(daily), monthly(daily)
    if is_btc:
        score, signals = compute_all(
            daily, w, m, onchain.get_valuation(), onchain.get_hashrate(),
            onchain.get_miners_revenue(), cfg)
    else:
        score, signals = compute_alt(daily, w, m, cfg)

    regime = detect(daily)
    decision = decide(regime, score)
    plan = optimize(daily, decision, score, capital, cfg)
    price = float(daily["close"].iloc[-1])

    payload = (price, regime, score, decision, plan, signals, symbol)
    if args.json:
        print(report.to_json(*payload))
    elif args.markdown:
        print(report.to_markdown(*payload))
    else:
        print(report.to_text(*payload))


if __name__ == "__main__":
    main()
