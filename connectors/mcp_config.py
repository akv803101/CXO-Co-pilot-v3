"""MCP server config builders — one per source type.

`server_for(source)` takes a single source entry (as parsed from sources.yaml)
and returns a stdio MCP server config dict:

    {"id": <source_id>, "command": <cmd>, "args": [...], "env": {...}}

The orchestrator spins one server up per active source and exposes its tools to
Claude as `mcp__<source_id>__*`. Adding a new source type = add a builder to
`_BUILDERS` — no other file changes.

Credentials are read from config (secrets.toml) here, never from sources.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import config

_SNOWFLAKE_SERVICE_CONFIG = str(Path(__file__).parent / "snowflake_service_config.yaml")


def _snowflake(source: dict[str, Any]) -> dict[str, Any]:
    # snowflake-labs-mcp: stdio by default, needs a read-only service-config file.
    # Credentials go through env (SNOWFLAKE_*) so they never appear in the process
    # argument list. The model qualifies tables as DB.SCHEMA.TABLE from sources.yaml.
    env = {
        "SNOWFLAKE_ACCOUNT": config.require("SNOWFLAKE_ACCOUNT"),
        "SNOWFLAKE_USER": config.require("SNOWFLAKE_USER"),
        "SNOWFLAKE_PASSWORD": config.require("SNOWFLAKE_PASSWORD"),
        "SNOWFLAKE_WAREHOUSE": config.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    }
    role = config.get("SNOWFLAKE_ROLE")
    if role:
        env["SNOWFLAKE_ROLE"] = str(role)
    return {
        "id": source["id"],
        "command": "uvx",
        "args": ["snowflake-labs-mcp", "--service-config-file", _SNOWFLAKE_SERVICE_CONFIG],
        "env": env,
    }


def _gsheets(source: dict[str, Any]) -> dict[str, Any]:
    env: dict[str, str] = {}
    sa_path = config.get("GOOGLE_SERVICE_ACCOUNT_PATH")
    if sa_path:
        env["SERVICE_ACCOUNT_PATH"] = str(sa_path)
    folder = config.get("DRIVE_FOLDER_ID")
    if folder:
        env["DRIVE_FOLDER_ID"] = str(folder)
    return {"id": source["id"], "command": "uvx", "args": ["mcp-google-sheets"], "env": env}


def _sql_url(server_pkg: str, url_key: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def build(source: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": source["id"],
            "command": "uvx",
            "args": [server_pkg, config.require(url_key)],
            "env": {},
        }

    return build


def _bigquery(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": source["id"],
        "command": "uvx",
        "args": ["mcp-bigquery", "--project", config.require("BQ_PROJECT_ID")],
        "env": {},
    }


# type -> builder
_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "snowflake": _snowflake,
    "gsheets": _gsheets,
    "bigquery": _bigquery,
    "postgres": _sql_url("mcp-postgres", "POSTGRES_URL"),
    "mysql": _sql_url("mcp-mysql", "MYSQL_URL"),
}

# Types that do not use an MCP server.
_BUILTIN = {"csv", "rest_api"}


def server_for(source: dict[str, Any]) -> dict[str, Any]:
    """Return the MCP server config for one source entry.

    Raises for csv/rest_api (handled by built-in/custom tools, not MCP) and for
    unknown types so misconfiguration fails loudly.
    """
    stype = source.get("type")
    if stype in _BUILTIN:
        raise ValueError(
            f"Source '{source['id']}' type '{stype}' uses a built-in tool, not an MCP server."
        )
    builder = _BUILDERS.get(stype)
    if builder is None:
        raise ValueError(f"Unsupported source type '{stype}' for source '{source['id']}'.")
    return builder(source)


def servers_for(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build MCP server configs for every MCP-backed source given."""
    out: list[dict[str, Any]] = []
    for src in sources:
        if src.get("type") in _BUILTIN:
            continue
        out.append(server_for(src))
    return out
