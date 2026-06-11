"""Tests del simulador de grid (series 1h sinteticas)."""
import numpy as np
import pandas as pd

from src.backtest.grid_sim import simulate_grid
from src.config import load_config
from src.grid.optimizer import GridPlan


def _plan(lower, upper, grids, side="neutral", sl=None, tp=None, be=None, inv=1000, lev=3):
    return GridPlan(bot_type=side, entry_trigger=None, lower=lower, upper=upper, grids=grids,
                    leverage=lev, investment=inv, stop_loss=sl, take_profit=tp,
                    net_pct_per_grid=0.003, break_even=be)


def _prices(closes, start="2022-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq="h", tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c})


def test_oscillation_makes_grid_profit():
    cfg = load_config()
    closes = []
    for _ in range(20):
        closes += list(np.linspace(61000, 58000, 10)) + list(np.linspace(58000, 64000, 10))
    plan = _plan(56000, 66000, 20, side="neutral", sl=53000, be=61000)
    res = simulate_grid(_prices(closes), plan, entry_price=61000, cfg=cfg)
    assert res.grid_profit > 0
    assert res.rounds > 0


def test_crash_hits_sl():
    cfg = load_config()
    closes = list(np.linspace(61000, 50000, 200))  # cae fuerte, rompe SL 53000
    plan = _plan(56000, 66000, 20, side="neutral", sl=53000, be=61000)
    res = simulate_grid(_prices(closes), plan, 61000, cfg)
    assert res.exit_reason == "SL"
    assert res.trend_pnl < 0   # posicion long acumulada en la caida


def test_flat_no_rounds():
    cfg = load_config()
    closes = [61000.0] * 100   # plano: sin cruces de nivel
    plan = _plan(56000, 66000, 20, side="neutral", sl=53000, be=61000)
    res = simulate_grid(_prices(closes), plan, 61000, cfg)
    assert res.rounds == 0


def test_long_captures_uptrend():
    cfg = load_config()
    closes = list(np.linspace(61000, 68000, 200))  # tendencia alcista pura
    plan = _plan(56000, 66000, 20, side="long", sl=53000, tp=70000)
    res = simulate_grid(_prices(closes), plan, 61000, cfg)
    assert res.pnl > 0   # el grid long gana con la tendencia a favor (antes daba ~0)


def test_short_captures_downtrend():
    cfg = load_config()
    closes = list(np.linspace(61000, 54000, 200))  # tendencia bajista pura
    plan = _plan(56000, 66000, 20, side="short", sl=70000, tp=53000)
    res = simulate_grid(_prices(closes), plan, 61000, cfg)
    assert res.pnl > 0   # el grid short gana con la tendencia bajista a favor
