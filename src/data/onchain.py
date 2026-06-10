"""Datos on-chain de fuentes gratuitas (sin API key).

- bitcoin-data.com (BGeometrics): MVRV Z-Score y Realized Price. Hasta ~15 req/dia sin
  token, que con el cache local (12h) es mas que suficiente.
- blockchain.info charts: hashrate y miners revenue (para Hash Ribbons y Puell).
"""
from __future__ import annotations

import pandas as pd
import requests

from src.config import load_config
from src.data.cache import load_cached, save_cached

_BD_URL = "https://bitcoin-data.com/v1/{metric}"
_BC_URL = "https://api.blockchain.info/charts/{chart}"
_HEADERS = {
    "User-Agent": "smart_grid/0.1 (https://github.com/ToxicDeimos/smart_grid)",
    "accept": "application/json",
}


def fetch_bitcoin_data(metric: str, value_field: str, use_cache: bool = True) -> pd.Series:
    """Serie historica de una metrica de bitcoin-data.com (sin API key).

    Args:
        metric: ruta del endpoint, p.ej. "mvrv-zscore" o "realized-price".
        value_field: nombre del campo de valor en el JSON, p.ej. "mvrvZscore".
    """
    cfg = load_config()
    key = f"bitcoindata_{metric}"
    if use_cache:
        c = load_cached(key, cfg["data"]["cache_ttl_hours"])
        if c is not None and not c.empty:
            return c.iloc[:, 0]

    r = requests.get(_BD_URL.format(metric=metric), headers=_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    s = pd.Series(
        {pd.to_datetime(row["d"], utc=True): float(row[value_field]) for row in data},
        name=value_field,
    ).sort_index()
    if use_cache and not s.empty:
        save_cached(key, s.to_frame())
    return s


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
    """MVRV Z-Score y Realized Price (bitcoin-data.com).

    Devuelve un DataFrame por fecha con columnas 'mvrv_z' y 'realized_price'. Si la
    fuente no esta disponible, devuelve un DataFrame vacio y esas senales se omiten
    del score (renormalizacion de pesos).
    """
    try:
        mvrv_z = fetch_bitcoin_data("mvrv-zscore", "mvrvZscore")
        realized = fetch_bitcoin_data("realized-price", "realizedPrice")
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame({"mvrv_z": mvrv_z, "realized_price": realized}).dropna(how="all")


def get_hashrate() -> pd.Series:
    return fetch_blockchain_chart("hash-rate")


def get_miners_revenue() -> pd.Series:
    return fetch_blockchain_chart("miners-revenue")
