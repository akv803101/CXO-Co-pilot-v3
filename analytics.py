"""Usage analytics — lightweight append-only query log + summaries.

Every answered question is logged as one JSON line. No external service; the log
lives next to the app and is gitignored. Powers the in-app Usage view.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOG_PATH = Path(__file__).parent / "usage_log.jsonl"


def log_query(
    user: str,
    model: str,
    question: str,
    sources_used: list[str],
    latency_s: float,
    tool_calls: int = 0,
    ok: bool = True,
    error: str = "",
) -> None:
    """Append one usage record. Never raises — analytics must not break a query."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user": user,
        "model": model,
        "question": question[:500],
        "sources_used": sources_used,
        "latency_s": round(latency_s, 2),
        "tool_calls": tool_calls,
        "ok": ok,
        "error": error[:300],
    }
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


def read_usage(limit: int | None = None) -> list[dict[str, Any]]:
    """Return usage records, newest first."""
    if not _LOG_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with _LOG_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows.reverse()
    return rows[:limit] if limit else rows


def summary() -> dict[str, Any]:
    """Aggregate stats across all logged queries."""
    rows = read_usage()
    if not rows:
        return {"total": 0}
    by_model: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_user: dict[str, int] = {}
    latencies: list[float] = []
    errors = 0
    for r in rows:
        by_model[r.get("model", "?")] = by_model.get(r.get("model", "?"), 0) + 1
        for s in r.get("sources_used", []):
            by_source[s] = by_source.get(s, 0) + 1
        by_user[r.get("user", "?")] = by_user.get(r.get("user", "?"), 0) + 1
        if isinstance(r.get("latency_s"), (int, float)):
            latencies.append(r["latency_s"])
        if not r.get("ok", True):
            errors += 1
    return {
        "total": len(rows),
        "errors": errors,
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "by_model": by_model,
        "by_source": by_source,
        "by_user": by_user,
    }
