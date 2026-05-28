"""Three-layer evaluation (CLAUDE.md Section 11). Run before every commit.

  Layer 1 — Output contract   (structural, run always, target 100%)
  Layer 2 — Calculation        (against EVAL data, target >=95%)
  Layer 3 — Source routing      (derived from sources.yaml, run always, target 100%)

Exit 1 if any Layer 1 or Layer 3 check fails, or Layer 2 pass rate < 95%.

Active sources and their capabilities are discovered from sources.yaml at startup —
nothing about routing is hardcoded here.
"""

from __future__ import annotations

import sys
from typing import Any, Callable

import orchestrator

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


# --------------------------------------------------------------- demo questions
def _questions() -> list[dict[str, Any]]:
    """The 5 demo question types (Section 6). Expected routing derived from caps."""
    sources = orchestrator.load_sources(active_only=True)
    by_cap: dict[str, str] = {}
    for s in sources:
        for cap in orchestrator._capabilities(s):
            by_cap.setdefault(cap, s["id"])
    all_ids = [s["id"] for s in sources]
    return [
        {
            "id": "Q1",
            "text": "Did we hit our revenue target this period? Where did we miss?",
            "must_include": [by_cap[c] for c in ("revenue",) if c in by_cap],
        },
        {
            "id": "Q2",
            "text": "What was the ROI of each marketing campaign by channel?",
            "must_include": [by_cap[c] for c in ("campaigns",) if c in by_cap],
        },
        {
            "id": "Q3",
            "text": "How healthy is our pipeline? Which deals are at risk?",
            "must_include": [by_cap[c] for c in ("pipeline",) if c in by_cap],
        },
        {
            "id": "Q4",
            "text": "Give me an executive brief across revenue, pipeline and campaigns.",
            "must_include": all_ids,
            "expect_slide_deck": True,
        },
        {
            "id": "Q5",
            "text": "Drill into that region — what drove the miss?",
            "must_include": [by_cap[c] for c in ("revenue",) if c in by_cap],
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
def layer2_checks(q: dict[str, Any], resp: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Calculation accuracy vs seeded EVAL data.

    Requires an EVAL schema / EVAL tabs with known round numbers (Section 11).
    Until those are seeded against live sources this returns SKIP per question —
    SKIP does not count against the 95% pass target.
    """
    return [(f"{q['id']} calc", SKIP, "seed EVAL data to enable")]


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
        for name, status, why in layer2_checks(q, resp):
            rows.append(("L2", name, status, why))
        for name, status, why in layer3_checks(q, resp):
            rows.append(("L3", f"{q['id']}:{name}", status, why))

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
