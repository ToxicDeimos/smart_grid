"""Tests del score de confluencia (incluida la renormalizacion de pesos)."""
from src.config import load_config
from src.signals.bottom_score import score_from_signals
from src.signals.price_signals import Signal


def test_score_renormalizes_missing():
    cfg = load_config()
    # Solo 200WMA (peso 12) y Mayer (peso 13) tienen datos; 200WMA en suelo.
    sigs = [
        Signal("200WMA", 60000, True, ""),
        Signal("Mayer Multiple", 0.9, False, ""),
        Signal("MVRV Z-Score", None, False, "sin datos"),
    ]
    bs = score_from_signals(sigs, cfg)
    assert "MVRV Z-Score" in bs.missing
    assert abs(bs.score - 48.0) < 0.1  # 12 / (12 + 13) = 48%


def test_score_all_floor():
    cfg = load_config()
    sigs = [
        Signal("200WMA", 1, True, ""),
        Signal("Mayer Multiple", 1, True, ""),
    ]
    assert score_from_signals(sigs, cfg).score == 100.0


def test_score_none_available():
    cfg = load_config()
    sigs = [Signal("MVRV Z-Score", None, False, "sin datos")]
    bs = score_from_signals(sigs, cfg)
    assert bs.score == 0.0
    assert "MVRV Z-Score" in bs.missing
