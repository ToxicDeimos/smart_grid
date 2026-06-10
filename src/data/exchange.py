"""Descarga de datos de mercado (OHLCV) via ccxt, con paginacion y cache local.

Fuente por defecto: Binance spot BTC/USDT (historia larga desde ~2017), necesaria
para la media de 200 semanas y el analisis de ciclo. Para el rango operativo actual
puede usarse el perpetual configurado.
"""
from __future__ import annotations

import time

import ccxt
import pandas as pd

from src.config import load_config
from src.data.cache import load_cached, save_cached

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]
_RESAMPLE_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _exchange(name: str):
    return getattr(ccxt, name)({"enableRateLimit": True})


def _to_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["timestamp", *_OHLCV_COLS])
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("date")[_OHLCV_COLS]


def fetch_ohlcv(
    symbol: str | None = None,
    timeframe: str = "1d",
    since: str | int | None = None,
    exchange: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Descarga OHLCV paginado y lo devuelve como DataFrame indexado por fecha (UTC).

    Args:
        symbol: par, p.ej. "BTC/USDT" (por defecto, el de config).
        timeframe: temporalidad nativa a pedir (recomendado "1d").
        since: fecha ISO "YYYY-MM-DD" o epoch-ms de inicio.
        exchange: id de ccxt (por defecto, el de config).
        use_cache: si True, usa/actualiza el cache parquet.
    """
    cfg = load_config()
    symbol = symbol or cfg["symbol"]
    exchange = exchange or cfg["exchange"]
    since = since if since is not None else cfg["data"]["history_start"]

    cache_key = f"{exchange}_{symbol.replace('/', '').replace(':', '')}_{timeframe}"
    if use_cache:
        cached = load_cached(cache_key, ttl_hours=cfg["data"]["cache_ttl_hours"])
        if cached is not None and not cached.empty:
            return cached

    ex = _exchange(exchange)
    since_ms = ex.parse8601(f"{since}T00:00:00Z") if isinstance(since, str) else int(since)
    tf_ms = ex.parse_timeframe(timeframe) * 1000
    now_ms = ex.milliseconds()

    rows: list = []
    cursor = since_ms
    while cursor < now_ms:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1][0] + tf_ms
        if len(batch) < 1000:
            break
        time.sleep(ex.rateLimit / 1000)

    df = _to_df(rows)
    if use_cache and not df.empty:
        save_cached(cache_key, df)
    return df


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Agrega OHLCV diario a una temporalidad mayor.

    rule: regla de pandas, p.ej. "W-MON" (semanal, cierre lunes) o "ME" (mensual).
    """
    return df.resample(rule).agg(_RESAMPLE_AGG).dropna(how="any")


def weekly(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV semanal (cierre domingo, convencion habitual de cripto)."""
    return resample(df, "W-SUN")


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV mensual."""
    return resample(df, "ME")
