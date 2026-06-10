#!/usr/bin/env python
"""Panel web de smart_grid (Flask).

Sirve el panel HTML y una API JSON que ejecuta el motor completo (senales -> score ->
regimen -> tipo de bot -> optimizador) y devuelve la recomendacion.

Lanzar:  python web/app.py    (o:  flask --app web/app.py run)
Luego abrir http://127.0.0.1:5000
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request  # noqa: E402

import pandas as pd  # noqa: E402

from src import report  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data import onchain  # noqa: E402
from src.data.exchange import fetch_ohlcv, monthly, weekly  # noqa: E402
from src.grid.bot_type import decide  # noqa: E402
from src.grid.optimizer import optimize  # noqa: E402
from src.regime.regime import detect  # noqa: E402
from src.signals.bottom_score import compute_all  # noqa: E402

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True


@app.route("/")
def index():
    cfg = load_config()
    return render_template(
        "index.html",
        default_capital=cfg["capital_usdt"],
        default_symbol=cfg["symbol"],
    )


@app.route("/api/analysis")
def api_analysis():
    cfg = load_config()
    try:
        capital = float(request.args.get("capital", cfg["capital_usdt"]))
        symbol = request.args.get("symbol", cfg["symbol"])
        is_btc = symbol.split("/")[0].upper() in ("BTC", "XBT")

        daily = fetch_ohlcv(symbol=symbol, timeframe="1d")
        w, m = weekly(daily), monthly(daily)
        if is_btc:
            valuation = onchain.get_valuation()
            hashrate = onchain.get_hashrate()
            miners_revenue = onchain.get_miners_revenue()
        else:
            valuation = pd.DataFrame()
            hashrate = pd.Series(dtype=float)
            miners_revenue = pd.Series(dtype=float)

        score, signals = compute_all(daily, w, m, valuation, hashrate, miners_revenue, cfg)
        regime = detect(daily)
        decision = decide(regime, score)
        plan = optimize(daily, decision, score, capital, cfg)
        if not is_btc:
            plan.warnings.insert(0, (
                f"Senales on-chain omitidas: son especificas de BTC. El score de {symbol} "
                "usa solo senales de precio (la validacion historica se hizo sobre BTC)."
            ))
        price = float(daily["close"].iloc[-1])

        data = report.to_dict(price, regime, score, decision, plan, signals, symbol)
        data["date"] = str(daily.index[-1].date())
        hist = daily["close"].tail(180)
        data["price_history"] = [
            {"date": d.strftime("%Y-%m-%d"), "close": round(float(c), 2)}
            for d, c in hist.items()
        ]
        return jsonify(data)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 400


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
