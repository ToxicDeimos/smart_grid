"""DCA inteligente: cuanto comprar BTC spot segun el score de suelo de ciclo.

Validado en scripts/backtest_dca.py: ponderar las compras por el score logra mejor precio
medio y ROI que el DCA plano (BTC 2021-2026: ROI +71.5% vs +50.4%, precio medio -12.3%).
La idea: cuanto mas barato esta BTC en su ciclo (score de suelo alto), mas se acumula.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DCAReco:
    score: float
    multiplier: float
    amount: float
    label: str


def multiplier(score: float) -> float:
    """Multiplicador de compra: 1x (score 0) -> 3x (score 100)."""
    return round(1.0 + 2.0 * (max(0.0, min(100.0, score)) / 100.0), 2)


def recommend(score: float, base_amount: float) -> DCAReco:
    """Cuanto comprar hoy: base_amount x multiplicador(score), con etiqueta cualitativa."""
    m = multiplier(score)
    if score >= 75:
        label = "Zona de suelo: acumula fuerte"
    elif score >= 50:
        label = "Acercandose a suelo: sobrepondera"
    elif score >= 25:
        label = "Territorio intermedio: DCA normal"
    else:
        label = "Caro / posible techo: compra minima"
    return DCAReco(score=score, multiplier=m, amount=round(base_amount * m, 2), label=label)
