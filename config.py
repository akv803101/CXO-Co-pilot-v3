"""Secrets and runtime-variable loading. This file's only job is config access.

Reads .streamlit/secrets.toml (via Streamlit when available, else plain TOML).
Brand/period/currency variables and all credentials live there — never hardcoded,
never in sources.yaml.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # tomllib is stdlib on 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

_SECRETS_PATH = Path(__file__).parent / ".streamlit" / "secrets.toml"

# Runtime brand/period tokens (CLAUDE.md Section 1) with safe display defaults.
_VAR_DEFAULTS: dict[str, str] = {
    "BRAND_NAME": "Demo Co",
    "BRAND_DESCRIPTION": "A demo company",
    "PERIOD": "Q1 FY25",
    "CURRENCY_SYMBOL": "$",
    "CURRENCY_SHORTHAND": "M/K",
}


@lru_cache(maxsize=1)
def _file_secrets() -> dict[str, Any]:
    if not _SECRETS_PATH.exists():
        return {}
    with _SECRETS_PATH.open("rb") as fh:
        return tomllib.load(fh)


def _st_secrets() -> dict[str, Any]:
    """Streamlit's secrets if running inside Streamlit, else {}."""
    try:
        import streamlit as st  # noqa: WPS433 (local import on purpose)

        return dict(st.secrets)
    except Exception:
        return {}


def get(key: str, default: Any = None) -> Any:
    """Look up a single secret/value. Precedence: env > Streamlit > file."""
    if key in os.environ:
        return os.environ[key]
    st_secrets = _st_secrets()
    if key in st_secrets:
        return st_secrets[key]
    return _file_secrets().get(key, default)


def require(key: str) -> str:
    val = get(key)
    if val is None or val == "":
        raise RuntimeError(
            f"Missing required secret '{key}'. Add it to .streamlit/secrets.toml."
        )
    return str(val)


def variables() -> dict[str, str]:
    """The Section 1 brand/period tokens, resolved at runtime with defaults."""
    return {name: str(get(name, default)) for name, default in _VAR_DEFAULTS.items()}
