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


def test_neutral_plan_range_around_price():
    cfg = load_config()
    daily = _df(list(np.linspace(60000, 61000, 300)))
    plan = optimize(daily, BotDecision("neutral", "x"), BottomScore(50, "x"), 2000, cfg)
    assert plan.bot_type == "neutral"
    assert plan.lower < 61000 < plan.upper
    assert plan.grids >= 2
    assert plan.investment == 2000


def test_long_plan_liquidation_below_lower():
    cfg = load_config()
    daily = _df(list(np.linspace(80000, 60000, 300)))
    plan = optimize(daily, BotDecision("long", "x"), BottomScore(70, "x"), 2000, cfg)
    assert plan.bot_type == "long"
    assert plan.liquidation.liq_price < plan.lower
    assert plan.grids >= 2
    assert isinstance(plan.warnings, list)
