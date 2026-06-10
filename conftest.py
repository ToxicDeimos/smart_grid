"""Hace que `src` sea importable al ejecutar pytest desde la raiz del proyecto."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
