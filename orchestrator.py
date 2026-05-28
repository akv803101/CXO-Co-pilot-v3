"""Claude API call + source routing. This file's only job is orchestration.

At startup it reads registry/sources.yaml and builds the system prompt and routing
rules dynamically — nothing source-specific is hardcoded. Output is always the JSON
shape defined in CLAUDE.md Section 6.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

import config
import llm
from mcp_host import McpHost

_SOURCES_PATH = Path(__file__).parent / "registry" / "sources.yaml"
MAX_TOOL_ITERS = 8

# Output contract keys (CLAUDE.md Section 6).
OUTPUT_KEYS = ("answer", "chart", "slide_deck", "sources_used", "follow_up_hints")
SLIDE_TRIGGER_WORDS = ("brief", "summary", "deck", "board")


# --------------------------------------------------------------------------- IO
def load_sources(active_only: bool = True) -> list[dict[str, Any]]:
    """Read every source from sources.yaml. The single source of truth."""
    with _SOURCES_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    sources = data.get("sources", [])
    if active_only:
        sources = [s for s in sources if s.get("active")]
    return sources


def _write_sources(data: dict[str, Any]) -> None:
    with _SOURCES_PATH.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def _capabilities(source: dict[str, Any]) -> list[str]:
    cap = source.get("capability", [])
    return [cap] if isinstance(cap, str) else list(cap)


# ----------------------------------------------------------------- prompt build
def _fill_tokens(text: str, vars_: dict[str, str]) -> str:
    for token, value in vars_.items():
        text = text.replace("{{" + token + "}}", value)
    return text


def _source_block(source: dict[str, Any], vars_: dict[str, str]) -> str:
    lines = [
        f"### Source id: {source['id']}",
        f"- Type: {source['type']}",
        f"- Label: {source.get('label', source['id'])}",
        f"- Capability: {', '.join(_capabilities(source))}",
    ]
    conn = source.get("connection") or {}
    db, schema = conn.get("database"), conn.get("schema")
    if db and schema:
        lines.append(f"- Fully-qualified table prefix: {db}.{schema}.<TABLE>")
    for table in source.get("tables", []):
        cols = table.get("columns") or []
        parts = []
        for c in cols:
            desc = c.get("description")
            parts.append(f"{c['name']} ({desc})" if desc else c["name"])
        lines.append(f"- Table `{table['name']}`: {table.get('description', '')}")
        if parts:
            lines.append(f"    columns: {', '.join(parts)}")
    return _fill_tokens("\n".join(lines), vars_)


def build_system_prompt(sources: list[dict[str, Any]]) -> str:
    """Build the full system prompt from active sources + runtime variables."""
    v = config.variables()
    routing = "\n".join(
        f"- Questions about {', '.join(_capabilities(s))} → query source `{s['id']}`"
        for s in sources
    )
    source_docs = "\n\n".join(_source_block(s, v) for s in sources)
    example = json.dumps(
        {
            "answer": "Plain-English response with figures, % change, and attribution.",
            "chart": {"type": "bar", "title": "Title", "x": ["A", "B"], "y": [1, 2]},
            "slide_deck": False,
            "sources_used": [s["id"] for s in sources[:1]],
            "follow_up_hints": ["Follow-up 1", "Follow-up 2"],
        },
        indent=2,
    )
    return f"""You are CXO Copilot for {v['BRAND_NAME']} — {v['BRAND_DESCRIPTION']}.
Active reporting period: {v['PERIOD']}. Currency: {v['CURRENCY_SYMBOL']} ({v['CURRENCY_SHORTHAND']}).

You answer executive business questions by querying live data through MCP tools.
There is no mock data. Query the right source(s), do all math yourself from raw rows,
and reply with direct, filler-free prose.

## Available data sources
{source_docs}

## Routing rules
Match the question intent to a source's capability, then query that source.
{routing}

## Using the data tools
Each source exposes MCP tools (named `<source_id>__<tool>`). To answer, CALL these
tools to fetch real rows — never invent numbers. If a source's tables/columns are
not listed above, first use its tools to discover the schema (list tables, describe
columns), then query. Only after you have the rows, compute the answer and reply
with the final JSON object.
A question spanning all active sources, or containing any of {SLIDE_TRIGGER_WORDS}, is an
executive brief: set slide_deck=true and include every queried source in sources_used.

## Calculation rules
- MCP tools return raw rows — you do all arithmetic. Infer the metric from the question.
- Show formula logic in plain English (e.g. "ROI = {v['CURRENCY_SYMBOL']}X revenue / {v['CURRENCY_SYMBOL']}Y spend = Z×").
- Round only the final displayed figure. Derive unknown metrics from first principles — never refuse.
- Chart values MUST equal the numbers in your answer.

## Multi-turn rule
Full conversation history is provided. On "you said" / "that region" / "the campaign",
extract the entity from the prior turn and re-query only the source needed.

## Error handling
If a source fails, return a partial answer from the others and flag the gap explicitly —
never crash. Use sources_used to list only sources that actually returned data.

## Output format — return ONLY this JSON object, nothing else:
{example}

Rules for the JSON:
- chart.type is one of "bar", "line", "none". When not "none", chart.x and chart.y have equal length.
- sources_used lists only sources actually queried (by their id), at least one item.
- follow_up_hints has exactly 2 items.
- slide_deck is a real boolean.
- End every answer with the 2 follow-up questions in follow_up_hints.
"""


# ------------------------------------------------------------------- live call
def _extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of a model reply (handles ```json fences / prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, depth = text.find("{"), 0
        if start != -1:
            for i in range(start, len(text)):
                depth += text[i] == "{"
                depth -= text[i] == "}"
                if depth == 0:
                    candidate = text[start : i + 1]
                    break
    if candidate is None:
        raise ValueError("No JSON object found in model response.")
    return json.loads(candidate)


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """Coerce a model payload into the strict output contract."""
    out = dict(payload)
    out.setdefault("answer", "")
    chart = out.get("chart") or {"type": "none"}
    if chart.get("type") not in ("bar", "line", "none"):
        chart["type"] = "none"
    if chart["type"] == "none":
        chart.setdefault("title", "")
        chart["x"], chart["y"] = [], []
    else:
        chart.setdefault("title", "")
        x, y = list(chart.get("x", [])), list(chart.get("y", []))
        n = min(len(x), len(y))
        chart["x"], chart["y"] = x[:n], y[:n]
    out["chart"] = chart
    out["slide_deck"] = bool(out.get("slide_deck", False))
    su = out.get("sources_used") or []
    out["sources_used"] = list(su) if isinstance(su, list) else [su]
    fh = out.get("follow_up_hints") or []
    out["follow_up_hints"] = (list(fh) + ["", ""])[:2]
    return out


def ask(
    question: str,
    history: list[dict[str, str]] | None = None,
    allowed_source_ids: list[str] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Answer one question. Returns the Section 6 JSON shape.

    history: prior turns as [{"role": "user"|"assistant", "content": str}, ...] —
             passed in full for multi-turn (Q5).
    allowed_source_ids: source gate. None = all active sources.
    model: "provider:model" selection (e.g. "groq:llama-3.3-70b-versatile").
           None = registry default. Live data tools are wired by the MCP host
           (next step); this call routes the prompt to the chosen provider.
    """
    sources = load_sources(active_only=True)
    if allowed_source_ids is not None:
        sources = [s for s in sources if s["id"] in set(allowed_source_ids)]
    if not sources:
        return normalize(
            {
                "answer": "No data sources are connected.",
                "chart": {"type": "none"},
                "slide_deck": False,
                "sources_used": [],
                "follow_up_hints": ["Connect a data source", "Add credentials"],
            }
        )

    system = build_system_prompt(sources)
    messages: list[dict[str, Any]] = list(history or []) + [
        {"role": "user", "content": question}
    ]
    provider = llm.get_provider(model)

    host: McpHost | None = None
    try:
        try:
            host = McpHost(sources, timeout=60)
        except Exception as exc:
            return normalize(
                {
                    "answer": f"Could not connect to the data sources: {exc}",
                    "chart": {"type": "none"},
                    "slide_deck": False,
                    "sources_used": [],
                    "follow_up_hints": [
                        "Add the source credentials to .streamlit/secrets.toml",
                        "Verify the source is active in sources.yaml",
                    ],
                }
            )
        tools = host.tools()
        for _ in range(MAX_TOOL_ITERS):
            result = provider.chat(
                system=system, messages=messages, tools=tools, max_tokens=2048
            )
            if not result.tool_calls:
                return normalize(_extract_json(result.text))
            messages.append(
                {"role": "assistant", "content": result.text, "tool_calls": result.tool_calls}
            )
            for tc in result.tool_calls:
                output = host.call(tc.name, tc.arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": output}
                )
        # Tool budget exhausted — force a final answer with no tools.
        final = provider.chat(system=system, messages=messages, max_tokens=2048)
        return normalize(_extract_json(final.text))
    finally:
        if host is not None:
            host.close()


# ----------------------------------------------- Section 13 backend functions
def on_source_connected(source_id: str, model: str | None = None) -> dict[str, Any]:
    """After a source is added: sample it and propose 3 exec questions (Section 13)."""
    sources = load_sources(active_only=False)
    source = next((s for s in sources if s["id"] == source_id), None)
    if source is None:
        raise ValueError(f"Source '{source_id}' not found in sources.yaml.")

    label = source.get("label", source_id)
    caps = ", ".join(_capabilities(source)) or "business data"
    generic = {
        "source_label": label,
        "summary": f"{label}: {caps} data.",
        "suggested_questions": [
            f"What are the headline {caps} numbers for {config.variables()['PERIOD']}?",
            f"Where are we over- or under-performing on {caps}?",
            f"What changed in {caps} versus the previous period?",
        ],
    }

    try:
        sample = _sample_rows(source)
        instruction = (
            "You have just been connected to a new data source. Read the sample, "
            "understand what it contains, and generate exactly 3 suggested questions "
            "a business executive would want to ask about this data. The questions "
            "must be specific to the actual data shown, not generic. Return JSON only "
            'as {"summary": "...", "suggested_questions": ["...","...","..."]}.'
        )
        result = llm.get_provider(model).chat(
            system="You generate executive questions about a data source. JSON only.",
            messages=[{"role": "user", "content": f"{instruction}\n\nSample:\n{sample}"}],
            max_tokens=512,
        )
        parsed = _extract_json(result.text)
        return {
            "source_label": label,
            "summary": parsed.get("summary", generic["summary"]),
            "suggested_questions": (parsed.get("suggested_questions") or [])[:3]
            or generic["suggested_questions"],
        }
    except Exception:
        # Sample fetch / model unavailable → generic questions from capability only.
        return generic


def _sample_rows(source: dict[str, Any]) -> str:
    """Describe the source's schema for the suggestion prompt (sample stand-in)."""
    return _source_block(source, config.variables())


def add_source(entry: dict[str, Any]) -> str:
    """Append a new source entry to sources.yaml (active). Returns its id.

    Used by the Connection Wizard (Section 12, Step 5). Credentials are NOT part
    of the entry — they go to secrets.toml via config.write_secret().
    """
    if "id" not in entry or "type" not in entry:
        raise ValueError("Source entry needs at least 'id' and 'type'.")
    with _SOURCES_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {"sources": []}
    data.setdefault("sources", [])
    if any(s.get("id") == entry["id"] for s in data["sources"]):
        raise ValueError(f"Source id '{entry['id']}' already exists.")
    entry.setdefault("active", True)
    entry.setdefault("schema_discovery", "both")
    data["sources"].append(entry)
    _write_sources(data)
    return entry["id"]


def set_source_domain(source_id: str, capability: list[str]) -> bool:
    """Update only the capability field of a source. Atomic full-file rewrite."""
    with _SOURCES_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    found = False
    for src in data.get("sources", []):
        if src.get("id") == source_id:
            src["capability"] = list(capability)
            found = True
            break
    if not found:
        raise ValueError(f"Source '{source_id}' not found — refusing to create a new entry.")
    _write_sources(data)
    return True
