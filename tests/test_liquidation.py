"""Tests del calculo de liquidacion del grid."""
from src.liquidation import estimate, initial_fraction


def test_long_trigger_at_lower():
    # trigger = lower => entrada full; liq ~ lower*(1 - 1/3 + mmr)
    liq = estimate("long", lower=49000, upper=150000, leverage=3, entry=49000, mmr=0.005)
    assert abs(liq.liq_price - 49000 * (1 - 1 / 3 + 0.005)) < 1.0
    assert liq.initial_fraction == 1.0  # todo el rango queda por encima del trigger


def test_long_entry_at_upper():
    liq = estimate("long", lower=40000, upper=80000, leverage=3, entry=80000, mmr=0.005)
    assert abs(liq.avg_entry - 60000) < 1.0          # (80000 + 40000) / 2
    assert liq.initial_fraction == 0.0               # nada por encima del trigger


def test_short_liquidates_above_entry():
    liq = estimate("short", lower=40000, upper=80000, leverage=3, entry=60000, mmr=0.005)
    assert liq.liq_price > liq.avg_entry


def test_initial_fraction_midpoint():
    assert abs(initial_fraction(60000, 40000, 80000, "long") - 0.5) < 1e-9
