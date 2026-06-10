"""Tests de las senales on-chain (datos sinteticos, sin red)."""
import numpy as np
import pandas as pd

from src.signals import onchain_signals as oc


def _series(values, start="2022-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D", tz="UTC")
    return pd.Series(values, index=idx)


def test_hash_ribbons_capitulation():
    hr = _series(np.linspace(200, 100, 120))  # hashrate cayendo => SMA30 < SMA60
    assert oc.signal_hash_ribbons(hr).in_floor_zone is True


def test_hash_ribbons_stable():
    hr = _series(np.linspace(100, 200, 120))  # hashrate subiendo
    assert oc.signal_hash_ribbons(hr).in_floor_zone is False


def test_puell_floor():
    rev = _series([100.0] * 399 + [30.0], start="2021-01-01")  # hoy << MA365
    sig = oc.signal_puell(rev, floor=0.5)
    assert sig.in_floor_zone is True
    assert sig.value < 0.5


def test_mvrv_z_no_data():
    sig = oc.signal_mvrv_z(pd.DataFrame(), floor=0.5)
    assert sig.value is None
    assert sig.in_floor_zone is False


def test_realized_price_zone():
    val = pd.DataFrame({"realized_price": [50000.0]})
    assert oc.signal_realized_price(val, price=40000.0).in_floor_zone is True   # ratio 0.8 < 1
    assert oc.signal_realized_price(val, price=60000.0).in_floor_zone is False  # ratio 1.2 > 1
