"""Carga de configuracion (config/config.yaml) y variables de entorno (.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "config.yaml"

# Carga .env si existe (ninguna clave es obligatoria en v1).
load_dotenv(ROOT / ".env")


@lru_cache(maxsize=8)
def load_config(path: str | None = None) -> dict:
    """Lee y cachea el YAML de configuracion."""
    cfg_path = Path(path) if path else CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_root() -> Path:
    """Raiz del proyecto (para resolver rutas de data/ y logs/)."""
    return ROOT
