"""Zugriff auf config.toml im Projektwurzelverzeichnis."""

import tomllib
from functools import cache
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"


@cache
def config() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as f:
        return tomllib.load(f)
