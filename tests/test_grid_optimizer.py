"""Tests del optimizador de grid (datos sinteticos)."""
import numpy as np
import pandas as pd

from src.config import load_config
from src.grid.bot_type import BotDecision
from src.grid.optimizer import optimize
from src.signals.bottom_score import BottomScore


def _df(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D", tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.02, "low": c * 0.98, "close": c})


def test_neutral_plan_range_sl_breakeven():
    cfg = load_config()
    daily = _df(list(np.linspace(60000, 61000, 300)))
    plan = optimize(daily, BotDecision("neutral", "x"), BottomScore(50, "x"), 2000, cfg)
    assert plan.bot_type == "neutral"
    assert plan.lower < 61000 < plan.upper
    assert plan.grids >= 2
    assert plan.investment == 2000
    assert plan.stop_loss < plan.lower                 # SL por debajo del rango
    assert plan.take_profit is None                    # neutral: TP por rondas, no de precio
    assert plan.lower < plan.break_even < plan.upper   # cierre en el equilibrio (centro)


def test_long_plan_sl_tp():
    cfg = load_config()
    daily = _df(list(np.linspace(80000, 60000, 300)))
    plan = optimize(daily, BotDecision("long", "x"), BottomScore(70, "x"), 2000, cfg)
    assert plan.bot_type == "long"
    assert plan.stop_loss < plan.lower
    assert plan.take_profit > plan.upper
    assert plan.grids >= 2
    assert isinstance(plan.warnings, list)


def test_short_plan_sl_tp():
    cfg = load_config()
    daily = _df(list(np.linspace(40000, 60000, 300)))
    plan = optimize(daily, BotDecision("short", "x"), BottomScore(20, "x"), 2000, cfg)
    assert plan.bot_type == "short"
    assert plan.stop_loss > plan.upper        # short: SL por encima
    assert plan.take_profit < plan.lower      # TP por debajo
