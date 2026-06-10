"""Score de confluencia de suelo de ciclo (termometro 0-100).

Combina las senales de precio y on-chain en un unico score ponderado. Las senales
sin datos se EXCLUYEN y su peso se redistribuye (renormalizacion), de modo que la
ausencia de una fuente no infla ni penaliza artificialmente el resultado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from src.signals import onchain_signals, price_signals
from src.signals.price_signals import Signal

# Nombre de senal -> clave de peso en config["weights"]
_WEIGHT_KEYS = {
    "200WMA": "below_200wma",
    "Mayer Multiple": "mayer_multiple",
    "Drawdown ATH": "drawdown",
    "RSI mensual": "rsi_monthly",
    "Bull Market Support Band": "bmsb",
    "MVRV Z-Score": "mvrv_z",
    "Realized Price": "realized_price",
    "Hash Ribbons": "hash_ribbons",
    "Puell Multiple": "puell",
}


@dataclass
class BottomScore:
    score: float                       # 0-100
    label: str
    active: list[str] = field(default_factory=list)   # senales en zona de suelo
    missing: list[str] = field(default_factory=list)  # senales sin datos (excluidas)


def _label(score: float, cfg: dict) -> str:
    for entry in cfg["score_labels"]:  # ordenado desc por 'min'
        if score >= entry["min"]:
            return entry["label"]
    return cfg["score_labels"][-1]["label"]


def score_from_signals(signals: list[Signal], cfg: dict) -> BottomScore:
    """Calcula el score 0-100 sobre las senales con datos (renormaliza pesos)."""
    weights = cfg["weights"]
    available = [s for s in signals if s.value is not None]
    missing = [s.name for s in signals if s.value is None]

    total = sum(weights[_WEIGHT_KEYS[s.name]] for s in available)
    if total == 0:
        return BottomScore(0.0, "sin datos suficientes", [], missing)

    earned = sum(weights[_WEIGHT_KEYS[s.name]] for s in available if s.in_floor_zone)
    score = round(100.0 * earned / total, 1)
    active = [s.name for s in available if s.in_floor_zone]
    return BottomScore(score, _label(score, cfg), active, missing)


def compute_all(daily: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame,
                valuation: pd.DataFrame, hashrate: pd.Series, miners_revenue: pd.Series,
                cfg: dict) -> tuple[BottomScore, list[Signal]]:
    """Calcula todas las senales (precio + on-chain) y el score de confluencia."""
    price = float(daily["close"].iloc[-1])
    signals = price_signals.compute(daily, weekly, monthly, cfg)
    signals += onchain_signals.compute(valuation, hashrate, miners_revenue, price, cfg)
    return score_from_signals(signals, cfg), signals
