"""Decision del tipo de bot de grid (Long / Short / Neutral).

Combina el regimen de mercado con el score de suelo de ciclo:
- score de suelo alto                -> Long  (apostar rebote desde suelo)
- regimen lateral                    -> Neutral
- tendencia bajista sin senal suelo  -> Short
- tendencia alcista                  -> Long
- transicion / bajista con score medio -> Neutral (cautela)
"""
from __future__ import annotations

from dataclasses import dataclass

from src.regime.regime import Regime
from src.signals.bottom_score import BottomScore


@dataclass
class BotDecision:
    bot_type: str   # "long" | "short" | "neutral"
    rationale: str


def decide(regime: Regime, bottom: BottomScore,
           long_score: float = 65.0, short_score: float = 40.0) -> BotDecision:
    score = bottom.score
    trend = regime.trend

    if score >= long_score:
        return BotDecision("long", f"score de suelo alto ({score:.0f}); apostar rebote desde suelo")
    if trend == "lateral":
        return BotDecision("neutral", f"regimen lateral (ADX {regime.adx}); grid neutral")
    if trend == "bajista" and score < short_score:
        return BotDecision("short", f"tendencia bajista sin senal de suelo (score {score:.0f})")
    if trend == "alcista":
        return BotDecision("long", f"tendencia alcista (ADX {regime.adx})")
    return BotDecision("neutral", f"transicion (tendencia {trend}, score {score:.0f}); grid neutral por cautela")
