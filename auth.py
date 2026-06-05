"""Email + password authentication with role-based access control.

Users live in .streamlit/users.yaml (gitignored); falls back to the committed
.example so the demo runs out of the box. Passwords are sha256 hex. Each user
has one or more roles; roles map to data capabilities, which gate which sources
the user can query.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml

_DIR = Path(__file__).parent / ".streamlit"
_USERS = _DIR / "users.yaml"
_USERS_EXAMPLE = _DIR / "users.yaml.example"

# Role → allowed data capabilities. "*" = all sources (no restriction).
ROLE_CAPABILITIES: dict[str, Any] = {
    "admin": "*",
    "exec": "*",
    "analyst": "*",
    "finance": {"revenue", "finance"},
    "sales": {"revenue", "pipeline", "custom"},
    "marketing": {"campaigns"},
}
ALL_ROLES = list(ROLE_CAPABILITIES)


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _load_users() -> list[dict[str, Any]]:
    path = _USERS if _USERS.exists() else _USERS_EXAMPLE
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("users", [])


def _write_users(users: list[dict[str, Any]]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    _USERS.write_text(yaml.safe_dump({"users": users}, sort_keys=False), encoding="utf-8")


def check(email: str, password: str) -> dict[str, Any] | None:
    """Return the user (without password) if creds match, else None."""
    digest = _hash(password)
    for user in _load_users():
        if user.get("email", "").lower() == email.strip().lower() and user.get(
            "password"
        ) == digest:
            return {
                "email": user["email"],
                "name": user.get("name", email),
                "roles": user.get("roles", []),
            }
    return None


def create_user(email: str, name: str, password: str, roles: list[str]) -> dict[str, Any]:
    """Register a new user. Raises ValueError on duplicate or bad input."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("Enter a valid email.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    users = _load_users()
    if any(u.get("email", "").lower() == email for u in users):
        raise ValueError("An account with that email already exists.")
    users.append(
        {"email": email, "name": name or email, "password": _hash(password),
         "roles": roles or ["analyst"]}
    )
    _write_users(users)
    return {"email": email, "name": name or email, "roles": roles or ["analyst"]}


def allowed_capabilities(roles: list[str]) -> Any:
    """Union of capabilities across roles. Returns "*" if any role is unrestricted."""
    caps: set[str] = set()
    for role in roles:
        rule = ROLE_CAPABILITIES.get(role)
        if rule == "*":
            return "*"
        if rule:
            caps |= set(rule)
    return caps
