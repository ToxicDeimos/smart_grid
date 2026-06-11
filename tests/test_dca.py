"""Tests del DCA inteligente."""
from src.dca import multiplier, recommend


def test_multiplier_range():
    assert multiplier(0) == 1.0
    assert multiplier(100) == 3.0
    assert multiplier(50) == 2.0
    assert multiplier(-10) == 1.0     # acotado
    assert multiplier(150) == 3.0     # acotado


def test_recommend_scales_with_score():
    lo = recommend(10, 100)
    hi = recommend(80, 100)
    assert hi.amount > lo.amount               # mas suelo -> compra mas
    assert hi.amount == 100 * multiplier(80)
    assert "suelo" in hi.label.lower()
