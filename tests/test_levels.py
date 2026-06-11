"""Tests del detector de soportes/resistencias."""
import pandas as pd

from src.signals.levels import cluster, nearest_levels, pivots


def _df(highs, lows):
    idx = pd.date_range("2022-01-01", periods=len(highs), freq="D", tz="UTC")
    return pd.DataFrame({"open": highs, "high": highs, "low": lows, "close": highs}, index=idx)


def test_cluster_groups_near():
    c = cluster([100, 101, 102, 200, 201], tol=0.05)
    assert len(c) == 2
    assert c[0][1] == 3   # 100,101,102 -> 3 toques
    assert c[1][1] == 2


def test_pivots_detects_peak_and_valley():
    highs = [10, 11, 12, 13, 20, 13, 12, 11, 10]
    lows = [9, 10, 11, 12, 19, 12, 11, 10, 9]
    sh, sl = pivots(_df(highs, lows), k=2)
    assert 20.0 in sh


def test_nearest_levels():
    sup = [(100, 3), (90, 2)]
    res = [(120, 2), (150, 3)]
    s, r = nearest_levels(110, sup, res)
    assert s[0] == 100
    assert r[0] == 120
