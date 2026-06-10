"""Datos on-chain de fuentes gratuitas (sin API key).

- Coin Metrics Community API v4: market cap, realized cap, supply, precio.
- blockchain.info charts: hashrate y miners revenue (para Hash Ribbons y Puell).
"""
from __future__ import annotations

import pandas as pd
import requests

from src.config import load_config
from src.data.cache import load_cached, save_cached

_CM_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
_BC_URL = "https://api.blockchain.info/charts/{chart}"
_HEADERS = {"User-Agent": "smart_grid/0.1 (https://github.com/ToxicDeimos/smart_grid)"}


def fetch_coinmetrics(metrics: list[str], asset: str = "btc", use_cache: bool = True) -> pd.DataFrame:
    """Descarga metricas de Coin Metrics Community (paginado) como DataFrame por fecha."""
    cfg = load_config()
    key = f"coinmetrics_{asset}_{'-'.join(metrics)}"
    if use_cache:
        c = load_cached(key, cfg["data"]["cache_ttl_hours"])
        if c is not None and not c.empty:
            return c

    params = {
        "assets": asset,
        "metrics": ",".join(metrics),
        "frequency": "1d",
        "page_size": 10000,
        "start_time": cfg["data"]["history_start"],
    }
    rows: list = []
    url = _CM_URL
    while url:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=30)
        r.raise_for_status()
        j = r.json()
        rows.extend(j.get("data", []))
        url = j.get("next_page_url")
        params = None  # next_page_url ya incluye los parametros

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["time"], utc=True).dt.normalize()
    df = df.set_index("date").drop(columns=["asset", "time"], errors="ignore")
    df = df.apply(pd.to_numeric, errors="coerce")
    if use_cache:
        save_cached(key, df)
    return df


def fetch_blockchain_chart(chart: str, use_cache: bool = True) -> pd.Series:
    """Descarga una serie de blockchain.info/charts/<chart> indexada por fecha."""
    cfg = load_config()
    key = f"blockchain_{chart}"
    if use_cache:
        c = load_cached(key, cfg["data"]["cache_ttl_hours"])
        if c is not None and not c.empty:
            return c.iloc[:, 0]

    r = requests.get(
        _BC_URL.format(chart=chart),
        params={"timespan": "all", "format": "json", "sampled": "false"},
        headers=_HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    values = r.json().get("values", [])
    if not values:
        return pd.Series(dtype=float)
    s = pd.Series(
        [v["y"] for v in values],
        index=pd.to_datetime([v["x"] for v in values], unit="s", utc=True),
        name=chart,
    )
    if use_cache:
        save_cached(key, s.to_frame())
    return s


def get_valuation() -> pd.DataFrame:
    """Market cap, realized cap, supply, precio, realized price y MVRV Z-Score."""
    try:
        df = fetch_coinmetrics(["CapMrktCurUSD", "CapRealUSD", "SplyCur", "PriceUSD"])
    except Exception:
        # Fuente no disponible (p.ej. 403 / requiere key). Las senales MVRV y Realized
        # Price se omitiran del score por falta de datos (renormalizacion de pesos).
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.dropna(subset=["CapMrktCurUSD", "CapRealUSD", "SplyCur"])
    df["realized_price"] = df["CapRealUSD"] / df["SplyCur"]
    df["mvrv"] = df["CapMrktCurUSD"] / df["CapRealUSD"]
    # MVRV Z-Score = (market cap - realized cap) / std(market cap)
    std = df["CapMrktCurUSD"].std()
    df["mvrv_z"] = (df["CapMrktCurUSD"] - df["CapRealUSD"]) / std
    return df


def get_hashrate() -> pd.Series:
    return fetch_blockchain_chart("hash-rate")


def get_miners_revenue() -> pd.Series:
    return fetch_blockchain_chart("miners-revenue")
