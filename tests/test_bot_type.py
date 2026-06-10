"""Tests de la decision de tipo de bot."""
from src.grid.bot_type import decide
from src.regime.regime import Regime
from src.signals.bottom_score import BottomScore


def test_long_on_high_score():
    d = decide(Regime("bajista", 30, ""), BottomScore(70, "x"))
    assert d.bot_type == "long"


def test_neutral_on_lateral():
    d = decide(Regime("lateral", 15, ""), BottomScore(40, "x"))
    assert d.bot_type == "neutral"


def test_short_on_downtrend_lowscore():
    d = decide(Regime("bajista", 30, ""), BottomScore(20, "x"))
    assert d.bot_type == "short"


def test_long_on_uptrend():
    d = decide(Regime("alcista", 30, ""), BottomScore(50, "x"))
    assert d.bot_type == "long"


def test_neutral_on_downtrend_midscore():
    d = decide(Regime("bajista", 30, ""), BottomScore(50, "x"))
    assert d.bot_type == "neutral"
