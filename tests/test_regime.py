"""Tests de deteccion de regimen (datos sinteticos)."""
import numpy as np
import pandas as pd

from src.regime import regime


def _df(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D", tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c})


def test_uptrend():
    r = regime.detect(_df(list(np.linspace(100, 300, 300))))
    assert r.trend == "alcista"


def test_downtrend():
    r = regime.detect(_df(list(np.linspace(300, 100, 300))))
    assert r.trend == "bajista"


def test_sideways():
    closes = [100 + (i % 2) for i in range(300)]  # oscilacion plana => ADX bajo
    r = regime.detect(_df(closes))
    assert r.trend == "lateral"
