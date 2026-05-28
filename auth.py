"""Email + password authentication (Section 12, Screen 1). No SSO, no roles.

Users live in .streamlit/users.yaml (gitignored); falls back to the committed
.example so the demo runs out of the box. Passwords are sha256 hex.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

_DIR = Path(__file__).parent / ".streamlit"
_USERS = _DIR / "users.yaml"
_USERS_EXAMPLE = _DIR / "users.yaml.example"


def _load_users() -> list[dict[str, Any]]:
    path = _USERS if _USERS.exists() else _USERS_EXAMPLE
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("users", [])


def check(email: str, password: str) -> dict[str, Any] | None:
    """Return the user dict (without password) if creds match, else None."""
    digest = hashlib.sha256(password.encode()).hexdigest()
    for user in _load_users():
        if user.get("email", "").lower() == email.strip().lower() and user.get(
            "password"
        ) == digest:
            return {"email": user["email"], "name": user.get("name", email)}
    return None
