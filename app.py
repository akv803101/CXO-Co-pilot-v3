"""CXO Copilot — Streamlit UI (CLAUDE.md Section 12). Layout/chat/charts only.

Login -> Onboarding canvas -> Connection wizard -> Chat. All data/answers come
from orchestrator.py; all credentials go through config.write_secret().
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import auth
import config
import llm
import orchestrator
import slides

st.set_page_config(page_title="CXO Copilot", page_icon="📊", layout="wide")

# Credential fields rendered per source type (Section 12, Step 2).
TYPE_OPTIONS = {
    "Snowflake": "snowflake",
    "Google Sheets": "gsheets",
    "BigQuery": "bigquery",
    "PostgreSQL / MySQL": "postgres",
    "CSV / Excel Upload": "csv",
    "REST API": "rest_api",
}
CRED_FIELDS = {
    "snowflake": ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_WAREHOUSE"],
    "gsheets": ["GOOGLE_SERVICE_ACCOUNT_PATH"],
    "bigquery": ["BQ_PROJECT_ID"],
    "postgres": ["POSTGRES_URL"],
    "mysql": ["MYSQL_URL"],
    "csv": [],
    "rest_api": ["REST_ENDPOINT", "REST_AUTH_TOKEN"],
}
DOMAIN_OPTIONS = {
    "Revenue & Sales": "revenue",
    "Pipeline & CRM": "pipeline",
    "Marketing & Campaigns": "campaigns",
    "Finance & P&L": "finance",
    "HR & People": "hr",
    "Other": "custom",
}


# ----------------------------------------------------------------- session init
def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("user", None)
    ss.setdefault("view", "chat")          # "chat" | "home" | "wizard"
    ss.setdefault("messages", [])          # [{role, content} | {role:'assistant', payload}]
    ss.setdefault("suggested", [])         # suggested question chips
    ss.setdefault("pending", None)         # queued message text (from a chip click)
    ss.setdefault("model", llm.default_option())  # "provider:model" selection


# ---------------------------------------------------------------------- helpers
def _active_sources() -> list[dict[str, Any]]:
    return orchestrator.load_sources(active_only=True)


def _history_for_api() -> list[dict[str, str]]:
    hist: list[dict[str, str]] = []
    for m in st.session_state.messages:
        if m["role"] == "user":
            hist.append({"role": "user", "content": m["content"]})
        else:
            hist.append({"role": "assistant", "content": m["payload"].get("answer", "")})
    return hist


def _queue(text: str) -> None:
    st.session_state.pending = text


def _new_chat() -> None:
    st.session_state.messages = []
    st.session_state.pending = None


def _refresh_suggestions() -> None:
    srcs = _active_sources()
    if not srcs:
        st.session_state.suggested = []
        return
    try:
        res = orchestrator.on_source_connected(
            srcs[0]["id"], model=st.session_state.get("model")
        )
        st.session_state.suggested = res.get("suggested_questions", [])[:3]
    except Exception:
        st.session_state.suggested = []


# ------------------------------------------------------------------ Screen 1
def _login() -> None:
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.markdown("## 📊 CXO Copilot")
        st.caption("Ask any business question in plain English.")
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", use_container_width=True):
                user = auth.check(email, password)
                if user:
                    st.session_state.user = user
                    _refresh_suggestions()
                    st.rerun()
                else:
                    st.error("Invalid email or password.")


# ------------------------------------------------------------------ Screen 2
def _canvas() -> None:
    st.markdown("<div style='height:18vh'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1, 1])
    with mid:
        st.markdown("<h1 style='text-align:center'>➕</h1>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center;font-size:1.2rem'>Connect a data source</p>",
            unsafe_allow_html=True,
        )
        if st.button("Connect a data source", use_container_width=True):
            st.session_state.view = "wizard"
            st.rerun()


# ------------------------------------------------------------ Connection wizard
def _wizard() -> None:
    st.subheader("Connect a data source")
    stype_label = st.selectbox("Step 1 — Source type", list(TYPE_OPTIONS))
    stype = TYPE_OPTIONS[stype_label]

    st.markdown("**Step 2 — Credentials**")
    creds: dict[str, str] = {}
    sheet_id = ""
    database = schema = ""
    if stype == "csv":
        st.file_uploader("Upload CSV / Excel", type=["csv", "xlsx"])
    else:
        for field in CRED_FIELDS.get(stype, []):
            is_secret = any(w in field for w in ("PASSWORD", "TOKEN", "KEY"))
            creds[field] = st.text_input(field, type="password" if is_secret else "default")
        if stype == "snowflake":
            database = st.text_input("Database")
            schema = st.text_input("Schema")
        if stype == "gsheets":
            sheet_id = st.text_input("Sheet ID (URL between /d/ and /edit)")
    st.caption("Schema (tables/columns) is auto-discovered from the source on connect.")

    domains = st.multiselect("Step 3 — Domain(s)", list(DOMAIN_OPTIONS))
    label = st.text_input("Step 4 — Name this source")

    c1, c2 = st.columns(2)
    if c1.button("Connect", type="primary", use_container_width=True):
        if not label or not domains:
            st.error("Pick at least one domain and give the source a name.")
            return
        source_id = label.strip().lower().replace(" ", "_").replace("/", "_")
        entry: dict[str, Any] = {
            "id": source_id,
            "type": stype,
            "label": label,
            "capability": [DOMAIN_OPTIONS[d] for d in domains],
            "active": True,
            "schema_discovery": "both",
            "tables": [],
        }
        if stype == "snowflake" and (database or schema):
            entry["connection"] = {"database": database, "schema": schema}
        if stype == "gsheets" and sheet_id:
            entry["sheet_id"] = sheet_id
        try:
            orchestrator.add_source(entry)
            for key, val in creds.items():
                if val:
                    config.write_secret(key, val)
            res = orchestrator.on_source_connected(
                source_id, model=st.session_state.get("model")
            )
            st.session_state.suggested = res.get("suggested_questions", [])[:3]
            st.session_state.view = "chat"
            st.success(f"Connected {label}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not connect: {exc}")
    if c2.button("Cancel", use_container_width=True):
        st.session_state.view = "chat"
        st.rerun()


# --------------------------------------------------------------- response render
def _render_payload(payload: dict[str, Any]) -> None:
    st.markdown(payload.get("answer", ""))

    chart = payload.get("chart") or {}
    ctype, x, y = chart.get("type"), chart.get("x") or [], chart.get("y") or []
    if ctype in ("bar", "line") and x and len(x) == len(y):
        df = pd.DataFrame({chart.get("title", "value"): y}, index=x)
        # Comparison table above the chart when 2+ entities are compared.
        if len(x) >= 2:
            st.table(pd.DataFrame({"Category": x, "Value": y}))
        if chart.get("title"):
            st.caption(chart["title"])
        (st.bar_chart if ctype == "bar" else st.line_chart)(df)

    if payload.get("slide_deck"):
        if st.button("Export as Deck", key=f"deck_{id(payload)}"):
            path = slides.build_deck(payload, config.variables()["BRAND_NAME"])
            with open(path, "rb") as fh:
                st.download_button(
                    "Download .pptx", fh, file_name="executive_brief.pptx",
                    key=f"dl_{id(payload)}",
                )

    hints = payload.get("follow_up_hints") or []
    if any(hints):
        cols = st.columns(len(hints))
        for i, hint in enumerate(hints):
            if hint:
                cols[i].button(hint, key=f"fu_{id(payload)}_{i}",
                               on_click=_queue, args=(hint,))

    used = payload.get("sources_used") or []
    if used:
        st.caption("Sources: " + "  ".join(f"`{s}`" for s in used))


# ------------------------------------------------------------------ Screen 3
def _sidebar() -> None:
    with st.sidebar:
        st.markdown(f"**📊 CXO Copilot**")
        st.caption(f"Signed in as {st.session_state.user['name']}")
        st.divider()
        options = llm.list_options()
        if options:
            current = st.session_state.model
            idx = options.index(current) if current in options else 0
            choice = st.selectbox(
                "Model", options, index=idx,
                format_func=lambda o: o + ("" if llm.provider_has_key(o) else "  (no key)"),
            )
            st.session_state.model = choice
            if not llm.provider_has_key(choice):
                st.caption("⚠️ Add this provider's API key to secrets.toml.")
        st.divider()
        st.button("🏠 Home", use_container_width=True,
                  on_click=lambda: st.session_state.update(view="home"))
        st.button("➕ New Chat", use_container_width=True, on_click=_new_chat)
        st.button("🔌 Add Data Source", use_container_width=True,
                  on_click=lambda: st.session_state.update(view="wizard"))
        st.divider()
        st.markdown("**Connected Sources**")
        for s in _active_sources():
            with st.expander(s.get("label", s["id"])):
                st.write(f"Type: `{s['type']}`")
                cap = s.get("capability", [])
                st.write("Capability: " + ", ".join(cap if isinstance(cap, list) else [cap]))
                for t in s.get("tables", []):
                    cols = [c["name"] for c in t.get("columns", [])]
                    st.write(f"`{t['name']}`: {', '.join(cols)}")
        st.divider()
        st.button("Log out", on_click=lambda: st.session_state.update(user=None))


def _chat() -> None:
    st.title("CXO Copilot")

    # Suggested-question chips at the top of a fresh chat.
    if not st.session_state.messages and st.session_state.suggested:
        st.caption("Try asking:")
        cols = st.columns(len(st.session_state.suggested))
        for i, q in enumerate(st.session_state.suggested):
            cols[i].button(q, key=f"sug_{i}", on_click=_queue, args=(q,))

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m["content"])
            else:
                _render_payload(m["payload"])

    typed = st.chat_input("Ask a business question…")
    text = typed or st.session_state.pending
    if text:
        st.session_state.pending = None
        st.session_state.messages.append({"role": "user", "content": text})
        with st.chat_message("user"):
            st.markdown(text)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    payload = orchestrator.ask(
                        text, history=_history_for_api()[:-1],
                        model=st.session_state.model,
                    )
                except Exception as exc:
                    payload = {
                        "answer": f"Something went wrong reaching the data: {exc}",
                        "chart": {"type": "none", "x": [], "y": []},
                        "slide_deck": False, "sources_used": [], "follow_up_hints": ["", ""],
                    }
            _render_payload(payload)
        st.session_state.messages.append({"role": "assistant", "payload": payload})
        st.rerun()


# ----------------------------------------------------------------------- main
def main() -> None:
    _init_state()
    if not st.session_state.user:
        _login()
        return

    _sidebar()
    view = st.session_state.view
    if view == "wizard":
        _wizard()
    elif view == "home" or not _active_sources():
        _canvas() if not _active_sources() else _home()
    else:
        _chat()


def _home() -> None:
    st.title("Overview")
    st.write("Connected sources:")
    for s in _active_sources():
        st.write(f"- **{s.get('label', s['id'])}** (`{s['type']}`)")
    if st.button("Open chat"):
        st.session_state.view = "chat"
        st.rerun()


if __name__ == "__main__":
    main()
