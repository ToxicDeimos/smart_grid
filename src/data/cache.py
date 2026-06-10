"""Cache local de DataFrames en CSV (carpeta data/).

Se usa CSV en lugar de parquet porque en algunos entornos Windows (App Control / WDAC)
la DLL de pyarrow esta bloqueada. CSV no tiene dependencias nativas y es portable.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from src.config import get_root, load_config


def _cache_dir() -> Path:
    cfg = load_config()
    d = get_root() / cfg["data"]["cache_dir"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(key: str) -> Path:
    return _cache_dir() / f"{key}.csv"


def load_cached(key: str, ttl_hours: float = 12) -> pd.DataFrame | None:
    """Devuelve el DataFrame cacheado si existe y no ha caducado; si no, None."""
    p = _path(key)
    if not p.exists():
        return None
    age_hours = (time.time() - p.stat().st_mtime) / 3600
    if age_hours > ttl_hours:
        return None
    try:
        return pd.read_csv(p, index_col=0, parse_dates=True)
    except Exception:
        return None


def save_cached(key: str, df: pd.DataFrame) -> None:
    """Guarda el DataFrame en CSV bajo data/<key>.csv."""
    df.to_csv(_path(key))
