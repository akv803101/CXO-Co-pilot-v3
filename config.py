"""Secrets and runtime-variable loading. This file's only job is config access.

Reads .streamlit/secrets.toml (via Streamlit when available, else plain TOML).
Brand/period/currency variables and all credentials live there — never hardcoded,
never in sources.yaml.
"""

from __future__ import annotations

import os
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


def _file_secrets() -> dict[str, Any]:
    # Read fresh each call so credentials entered through the UI at runtime take
    # effect immediately, without a restart.
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
    """Look up a single secret/value. Precedence: env > file (fresh) > Streamlit.

    File comes before st.secrets because Streamlit caches secrets at startup;
    reading the file lets UI-entered credentials apply without a restart.
    """
    if key in os.environ:
        return os.environ[key]
    file_secrets = _file_secrets()
    if key in file_secrets:
        return file_secrets[key]
    return _st_secrets().get(key, default)


def require(key: str) -> str:
    val = get(key)
    if val is None or val == "":
        raise RuntimeError(
            f"Missing required secret '{key}'. Add it to .streamlit/secrets.toml."
        )
    return str(val)


def write_secret(key: str, value: str) -> None:
    """Persist one credential to .streamlit/secrets.toml (created if absent).

    Credentials are written here only — never kept in UI state (Section 12).
    Minimal TOML writer: upserts a top-level key as a quoted string.
    """
    _SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if _SECRETS_PATH.exists():
        lines = _SECRETS_PATH.read_text(encoding="utf-8").splitlines()
    safe = str(value).replace("\\", "\\\\").replace('"', '\\"')
    new_line = f'{key} = "{safe}"'
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key} ") or line.strip().startswith(f"{key}="):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    _SECRETS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def variables() -> dict[str, str]:
    """The Section 1 brand/period tokens, resolved at runtime with defaults."""
    return {name: str(get(name, default)) for name, default in _VAR_DEFAULTS.items()}
