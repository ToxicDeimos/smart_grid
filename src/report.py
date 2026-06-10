"""Ensamblado de la recomendacion final en texto, markdown o JSON."""
from __future__ import annotations

import json

from src.grid.bot_type import BotDecision
from src.grid.optimizer import GridPlan
from src.regime.regime import Regime
from src.signals.bottom_score import BottomScore
from src.signals.price_signals import Signal

_DISCLAIMER = (
    "No es asesoramiento financiero. Un grid de futuros apalancado puede liquidar tu "
    "capital; revisa el precio de liquidacion que muestra Pionex al crear el bot. "
    "N pequeno (3-4 ciclos): marco de gestion de riesgo, no edge demostrado."
)


def _money(x: float | None) -> str:
    """Formato de precio con decimales adaptados a la escala (BTC vs alts baratos)."""
    if x is None:
        return "-"
    if abs(x) >= 1000:
        return f"${x:,.0f}"
    if abs(x) >= 1:
        return f"${x:,.2f}"
    return f"${x:,.4f}"


def _tp_line(plan: GridPlan) -> str:
    """Linea de Take Profit (direccional) o de cierre en equilibrio (neutral)."""
    if plan.take_profit is not None:
        return f"  Take Profit:             {_money(plan.take_profit)}"
    return f"  Cierre (equilibrio):     {_money(plan.break_even)}  (TP por rondas de arbitraje)"


def to_dict(price: float, regime: Regime, bottom: BottomScore, decision: BotDecision,
            plan: GridPlan, signals: list[Signal], symbol: str = "BTC/USDT") -> dict:
    return {
        "symbol": symbol,
        "price": round(price, 6),
        "regime": {"trend": regime.trend, "adx": regime.adx},
        "bottom_score": {
            "score": bottom.score, "label": bottom.label,
            "active": bottom.active, "missing": bottom.missing,
        },
        "bot_type": plan.bot_type,
        "rationale": decision.rationale,
        "plan": {
            "entry_trigger": plan.entry_trigger,
            "lower": plan.lower,
            "upper": plan.upper,
            "grids": plan.grids,
            "leverage": plan.leverage,
            "investment": plan.investment,
            "stop_loss": plan.stop_loss,
            "take_profit": plan.take_profit,
            "break_even": plan.break_even,
            "net_pct_per_grid": plan.net_pct_per_grid,
            "warnings": plan.warnings,
        },
        "signals": [
            {"name": s.name, "floor": s.in_floor_zone, "detail": s.detail} for s in signals
        ],
    }


def to_json(*args, **kwargs) -> str:
    return json.dumps(to_dict(*args, **kwargs), indent=2, ensure_ascii=False)


def to_text(price: float, regime: Regime, bottom: BottomScore, decision: BotDecision,
            plan: GridPlan, signals: list[Signal], symbol: str = "BTC/USDT") -> str:
    trig = "al precio actual" if plan.entry_trigger is None else _money(plan.entry_trigger)
    lines = [
        "=" * 66,
        f"  RECOMENDACION DE GRID  -  {symbol}  {_money(price)}",
        "=" * 66,
        f"  Regimen:          {regime.trend.upper()} (ADX {regime.adx})",
        f"  Score de suelo:   {bottom.score}/100 - {bottom.label}",
        f"  Senales en suelo: {', '.join(bottom.active) if bottom.active else 'ninguna'}",
    ]
    if bottom.missing:
        lines.append(f"  (sin datos:       {', '.join(bottom.missing)})")
    lines += [
        "-" * 66,
        f"  >> BOT RECOMENDADO: {plan.bot_type.upper()}",
        f"     {decision.rationale}",
        "-" * 66,
        f"  Activacion (trigger):    {trig}",
        f"  Rango:                   {_money(plan.lower)}  -  {_money(plan.upper)}",
        f"  Num. de grids:           {plan.grids}",
        f"  Apalancamiento:          {plan.leverage:.0f}x",
        f"  Inversion:               {_money(plan.investment)}",
        f"  Stop Loss:               {_money(plan.stop_loss)}",
        _tp_line(plan),
        f"  Ganancia neta/grid:      ~{plan.net_pct_per_grid * 100:.2f}%",
    ]
    if plan.warnings:
        lines.append("-" * 66)
        lines.append("  AVISOS:")
        lines += [f"   - {w}" for w in plan.warnings]
    lines += ["=" * 66, f"  {_DISCLAIMER}"]
    return "\n".join(lines)


def to_markdown(price: float, regime: Regime, bottom: BottomScore, decision: BotDecision,
                plan: GridPlan, signals: list[Signal], symbol: str = "BTC/USDT") -> str:
    trig = "al precio actual" if plan.entry_trigger is None else _money(plan.entry_trigger)
    md = [
        f"# Recomendacion de grid — {symbol} {_money(price)}",
        "",
        f"- **Regimen:** {regime.trend} (ADX {regime.adx})",
        f"- **Score de suelo:** {bottom.score}/100 — {bottom.label}",
        f"- **Senales en suelo:** {', '.join(bottom.active) if bottom.active else 'ninguna'}",
        "",
        f"## Bot recomendado: {plan.bot_type.upper()}",
        f"_{decision.rationale}_",
        "",
        "| Parametro | Valor |",
        "|---|---|",
        f"| Activacion | {trig} |",
        f"| Rango | {_money(plan.lower)} – {_money(plan.upper)} |",
        f"| Nº de grids | {plan.grids} |",
        f"| Apalancamiento | {plan.leverage:.0f}x |",
        f"| Inversion | {_money(plan.investment)} |",
        f"| Stop Loss | {_money(plan.stop_loss)} |",
        (f"| Take Profit | {_money(plan.take_profit)} |" if plan.take_profit is not None
         else f"| Cierre (equilibrio) | {_money(plan.break_even)} (TP por rondas) |"),
        f"| Ganancia neta/grid | ~{plan.net_pct_per_grid * 100:.2f}% |",
    ]
    if plan.warnings:
        md += ["", "### Avisos"] + [f"- {w}" for w in plan.warnings]
    md += ["", f"> {_DISCLAIMER}"]
    return "\n".join(md)
