"""Three-layer evaluation (CLAUDE.md Section 11). Run before every commit.

  Layer 1 — Output contract   (structural, run always, target 100%)
  Layer 2 — Calculation        (against EVAL data, target >=95%)
  Layer 3 — Source routing      (derived from sources.yaml, run always, target 100%)

Exit 1 if any Layer 1 or Layer 3 check fails, or Layer 2 pass rate < 95%.

Active sources and their capabilities are discovered from sources.yaml at startup —
nothing about routing is hardcoded here.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

import orchestrator

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
_FACTS_PATH = Path(__file__).parent / "registry" / "eval_facts.yaml"


# --------------------------------------------------------------- demo questions
def _questions() -> list[dict[str, Any]]:
    """The 5 demo question TYPES (Section 6), adapted to the active dataset.

    Routing is derived from the live sources: the revenue-capability source (or
    the first source) handles aggregation/metric/drill-down; a second source
    handles the count; the executive brief federates across all active sources.
    The wording is generic so it works on whatever tables are connected
    (verified here against SNOWFLAKE_SAMPLE_DATA.TPCH_SF1000: orders + customer).
    """
    sources = orchestrator.load_sources(active_only=True)
    by_cap: dict[str, str] = {}
    for s in sources:
        for cap in orchestrator._capabilities(s):
            by_cap.setdefault(cap, s["id"])
    all_ids = [s["id"] for s in sources]
    rev = by_cap.get("revenue") or (all_ids[0] if all_ids else None)
    other = next((i for i in all_ids if i != rev), rev)
    return [
        {  # Q1 — aggregation / "did we hit the number"
            "id": "Q1",
            "text": "How many orders are in the orders table? Use SELECT COUNT(*).",
            "must_include": [rev] if rev else [],
        },
        {  # Q2 — derived metric (sum/ratio) computed from raw rows
            "id": "Q2",
            "text": "What is the total value of all orders? Compute SUM(o_totalprice) "
                    "from the orders table.",
            "must_include": [rev] if rev else [],
        },
        {  # Q3 — count against a different source
            "id": "Q3",
            "text": "How many customers are in the customer table? Use SELECT COUNT(*).",
            "must_include": [other] if other else [],
        },
        {  # Q4 — executive brief: federate all sources + trigger a deck
            "id": "Q4",
            "text": "Give me an executive brief summarizing the orders and customers data.",
            "must_include": all_ids,
            "expect_slide_deck": True,
        },
        {  # Q5 — drill-down follow-up (multi-turn, re-query one source)
            "id": "Q5",
            "text": "Now break that order count down by order priority (o_orderpriority).",
            "must_include": [rev] if rev else [],
            "multi_turn": True,
        },
    ]


# ------------------------------------------------------------------- Layer 1
def layer1_checks(resp: dict[str, Any]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    def check(name: str, ok: bool, why: str = "") -> None:
        out.append((name, PASS if ok else FAIL, "" if ok else why))

    check("required keys", all(k in resp for k in orchestrator.OUTPUT_KEYS),
          f"missing {[k for k in orchestrator.OUTPUT_KEYS if k not in resp]}")
    chart = resp.get("chart", {})
    check("chart type valid", chart.get("type") in ("bar", "line", "none"),
          f"got {chart.get('type')!r}")
    if chart.get("type") != "none":
        check("chart x/y aligned", len(chart.get("x", [])) == len(chart.get("y", [])),
              f"x={len(chart.get('x', []))} y={len(chart.get('y', []))}")
    check("sources non-empty", isinstance(resp.get("sources_used"), list)
          and len(resp["sources_used"]) >= 1, "sources_used empty")
    check("two follow-ups", len(resp.get("follow_up_hints", [])) == 2,
          f"got {len(resp.get('follow_up_hints', []))}")
    check("slide_deck boolean", isinstance(resp.get("slide_deck"), bool),
          f"got {type(resp.get('slide_deck')).__name__}")
    return out


# ------------------------------------------------------------------- Layer 3
def layer3_checks(q: dict[str, Any], resp: dict[str, Any]) -> list[tuple[str, str, str]]:
    used = set(resp.get("sources_used", []))
    out: list[tuple[str, str, str]] = []
    for required in q["must_include"]:
        ok = required in used
        out.append((f"routes to {required}", PASS if ok else FAIL,
                    "" if ok else f"sources_used={sorted(used)}"))
    if q.get("expect_slide_deck"):
        ok = resp.get("slide_deck") is True
        out.append(("slide_deck triggered", PASS if ok else FAIL,
                    "" if ok else "slide_deck not true"))
    return out


# ------------------------------------------------------------------- Layer 2
def _load_eval_facts() -> list[dict[str, Any]]:
    if not _FACTS_PATH.exists():
        return []
    data = yaml.safe_load(_FACTS_PATH.read_text(encoding="utf-8")) or {}
    return data.get("facts", [])


def _numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in re.findall(r"-?\d[\d,]*\.?\d*", text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _number_matches(answer: str, expect: float, tolerance: float) -> bool:
    """Deterministic: does any number in the answer match expect within tolerance?"""
    expect = float(expect)
    allow = max(float(tolerance), float(tolerance) * abs(expect))
    return any(abs(n - expect) <= allow for n in _numbers(answer))


def layer2_run(model: str | None = None) -> list[tuple[str, str, str, str]]:
    """Run known-answer checks from registry/eval_facts.yaml (deterministic)."""
    facts = _load_eval_facts()
    if not facts:
        return [("L2", "(no eval_facts.yaml)", SKIP, "add registry/eval_facts.yaml to enable")]
    rows: list[tuple[str, str, str, str]] = []
    for fact in facts:
        q = fact["question"]
        try:
            resp = orchestrator.ask(q, model=model)
        except Exception as exc:
            rows.append(("L2", q[:45], FAIL, f"ask() raised: {exc}"))
            continue
        ok = _number_matches(resp.get("answer", ""), fact["expect"], fact.get("tolerance", 0))
        rows.append(
            ("L2", q[:45], PASS if ok else FAIL,
             "" if ok else f"expected {fact['expect']}, got: {resp.get('answer', '')[:80]}")
        )
    return rows


# ---------------------------------------------------------------------- runner
def run() -> int:
    questions = _questions()
    history: list[dict[str, str]] = []
    rows: list[tuple[str, str, str, str]] = []  # layer, q, status, why

    for q in questions:
        try:
            resp = orchestrator.ask(
                q["text"], history=history if q.get("multi_turn") else None
            )
        except Exception as exc:  # live call needs creds — report, don't crash
            rows.append(("L1", q["id"], FAIL, f"ask() raised: {exc}"))
            rows.append(("L3", q["id"], FAIL, f"ask() raised: {exc}"))
            continue
        history += [{"role": "user", "content": q["text"]},
                    {"role": "assistant", "content": resp.get("answer", "")}]
        for name, status, why in layer1_checks(resp):
            rows.append(("L1", f"{q['id']}:{name}", status, why))
        for name, status, why in layer3_checks(q, resp):
            rows.append(("L3", f"{q['id']}:{name}", status, why))

    # Layer 2 — deterministic known-answer checks (own questions, not Q1–Q5)
    rows.extend(layer2_run())

    # ---- report
    print("\n=== CXO Copilot eval report ===")
    for layer, q, status, why in rows:
        line = f"[{layer}] {status:4} {q}"
        print(line + (f"  — {why}" if why else ""))

    l1_fail = [r for r in rows if r[0] == "L1" and r[2] == FAIL]
    l3_fail = [r for r in rows if r[0] == "L3" and r[2] == FAIL]
    l2 = [r for r in rows if r[0] == "L2" and r[2] != SKIP]
    l2_pass_rate = (sum(r[2] == PASS for r in l2) / len(l2)) if l2 else 1.0

    print("\n--- summary ---")
    print(f"Layer 1: {'PASS' if not l1_fail else f'FAIL ({len(l1_fail)})'}")
    print(f"Layer 2: {l2_pass_rate*100:.0f}% ({'skipped' if not l2 else 'scored'})")
    print(f"Layer 3: {'PASS' if not l3_fail else f'FAIL ({len(l3_fail)})'}")

    if l1_fail or l3_fail or l2_pass_rate < 0.95:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run())
