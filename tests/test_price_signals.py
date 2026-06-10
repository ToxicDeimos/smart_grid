"""Tests de las senales de precio (datos sinteticos, sin red)."""
import numpy as np
import pandas as pd

from src.signals import price_signals as ps


def _daily(prices):
    idx = pd.date_range("2020-01-01", periods=len(prices), freq="D", tz="UTC")
    return pd.DataFrame(
        {"open": prices, "high": prices, "low": prices, "close": prices, "volume": 1.0},
        index=idx,
    )


def test_rsi_bounds():
    up = pd.Series(np.arange(1, 100, dtype=float))
    assert ps.rsi(up).iloc[-1] > 90
    down = pd.Series(np.arange(100, 1, -1, dtype=float))
    assert ps.rsi(down).iloc[-1] < 10


def test_drawdown_floor():
    # sube de 10 a 100 y cae a 25 => -75% desde ATH
    prices = list(np.linspace(10, 100, 50)) + list(np.linspace(100, 25, 50))
    daily = _daily(prices)
    sig = ps.signal_drawdown(daily, price=25.0, floor_pct=-0.70)
    assert sig.in_floor_zone is True
    assert sig.value < -0.70


def test_mayer_floor():
    # precio muy por debajo de la 200DMA (~100) => Mayer ~0.5 < 0.8
    daily = _daily([100.0] * 200 + [50.0])
    sig = ps.signal_mayer(daily, price=50.0, floor=0.8)
    assert sig.in_floor_zone is True
    assert sig.value < 0.8


def test_200wma_zone():
    idx = pd.date_range("2018-01-01", periods=250, freq="W-SUN", tz="UTC")
    weekly = pd.DataFrame({"close": [100.0] * 250}, index=idx)
    assert ps.signal_200wma(weekly, price=80.0).in_floor_zone is True
    assert ps.signal_200wma(weekly, price=120.0).in_floor_zone is False


def test_200wma_insufficient_data():
    idx = pd.date_range("2022-01-01", periods=50, freq="W-SUN", tz="UTC")
    weekly = pd.DataFrame({"close": [100.0] * 50}, index=idx)
    sig = ps.signal_200wma(weekly, price=80.0)
    assert sig.value is None
    assert sig.in_floor_zone is False
