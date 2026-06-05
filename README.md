<div align="center">

# 📊 CXO Copilot

### Ask any business question in plain English. Get answers, charts, and slide decks — instantly.

<br/>

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![MCP](https://img.shields.io/badge/Data-MCP-6E56CF)
![Multi--model](https://img.shields.io/badge/LLM-Anthropic%20%7C%20OpenAI%20%7C%20Groq-000000)
![Status](https://img.shields.io/badge/Snowflake-live%20verified-29B5E8?logo=snowflake&logoColor=white)

<br/>

*An AI analyst for executives — built by **IntelliBridge**.*

</div>

---

## Overview

**CXO Copilot turns a plain-English question into a sourced, calculated answer.**

Connect your data once, then just ask. Behind the scenes it picks the right source, runs live queries through **MCP**, does the math itself, and replies with clean prose, a chart, a comparison table, and — for executive briefs — an exportable slide deck. Run it on the **LLM of your choice** and switch models per chat.

```
        ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  "Did  │   CXO        │ →   │  route +     │ →   │  Snowflake   │
  we    │   Copilot    │     │  query (MCP) │     │  Sheets · …  │
  hit   │              │ ←   │  do the math │ ←   │  live rows   │
  goal?"└──────────────┘     └──────────────┘     └──────────────┘
              │
              ▼   answer · chart · comparison table · 📑 deck
```

### Why it's different
- 🔌 **Live data, no mocks** — every number comes from your real source via MCP
- 🧠 **Any LLM** — Anthropic, OpenAI, Groq, or any OpenAI-compatible provider; pick per chat
- 🗂 **Source-agnostic** — one `registry/sources.yaml`; add / edit / remove sources from the UI
- 📊 **Boardroom-ready output** — prose + bar/line charts + comparison tables + `.pptx` export
- 🔁 **Cross-source federation** — answer spans multiple sources; a failing one is skipped, not fatal
- 🔐 **Secrets stay local** — keys entered in-app, written only to gitignored `secrets.toml`
- 👥 **Login, sign-up & role-based access** — roles gate which sources each user can query
- 📈 **Usage analytics** + ✅ **three-layer evaluation** baked in

---

## ✅ What's live

| Capability | Status |
|---|---|
| **Snowflake** (live queries) | ✅ Verified end-to-end against real data |
| **Anthropic** (Claude) & **Groq** (Llama) | ✅ Verified live |
| OpenAI & other OpenAI-compatible providers | ⚙️ Supported — add a key to use |
| Google Sheets · Postgres · MySQL · BigQuery | ⚙️ Wired & connection-ready — pending live creds |
| Charts · comparison tables · usage analytics | ✅ Working |
| Login · sign-up · role-based access (RBAC) | ✅ Working |
| Styled `.pptx` deck export (offline) | ✅ Working — 16:9, branded, rendered chart |
| Gamma deck export | ⚙️ Built — add a Gamma API key to enable |

---

## Architecture

```
app.py            Streamlit UI — login, connection wizard, chat, charts, usage
orchestrator.py   Builds the prompt from sources.yaml; runs the tool-call loop
                  + on_source_connected / set_source_domain / add_source / remove_source
llm/              Provider-agnostic LLM layer
  base.py            one chat() contract (text + tool calls)
  anthropic_provider.py   native Claude adapter
  openai_provider.py      OpenAI-compatible (OpenAI, Groq, Together, Fireworks, local)
mcp_host.py       Synchronous stdio MCP client — spawns servers, runs the tool loop
connectors/mcp_config.py   MCP server config per source type
config.py         Secrets (global + per-source), read fresh each call
analytics.py      Append-only usage log + summaries
slides.py         Offline .pptx deck export
eval.py           Three-layer evaluation
registry/
  sources.yaml       single source of truth for data sources (no credentials)
  models.yaml        pluggable LLM provider/model registry
  eval_facts.yaml    known-answer checks for eval Layer 2
.streamlit/
  secrets.toml       credentials (gitignored)
  users.yaml         app login users (gitignored)
```

> **Design rule:** each file has one job. Credentials live only in `secrets.toml`; source structure only in `sources.yaml`.

---

## Quickstart

Requires Python ≥ 3.10 and [`uv`](https://github.com/astral-sh/uv) (for the `uvx` MCP servers).

```bash
git clone https://github.com/akv803101/CXO-Co-pilot-v3.git
cd CXO-Co-pilot-v3

uv venv --python 3.12
uv pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add keys/creds
cp .streamlit/users.yaml.example  .streamlit/users.yaml      # app logins

uv run streamlit run app.py        # → http://localhost:8501
```

Demo logins: **`admin@demo.co` / `admin123`** (all sources) · `sales@demo.co` / `sales123` (revenue/pipeline) · `marketing@demo.co` / `marketing123` (campaigns) — or **Sign up** to self-register with a role. Roles gate which sources a user can query (`auth.ROLE_CAPABILITIES`).

---

## Using it

**Connect a source** — Sidebar → **Add Data Source** → choose type → enter creds, database/schema, tables → pick domain → **Connect**. Use **✏️ Edit** to view/fix values, **🗑 Remove** to delete.

**Choose a model & add a key** — Sidebar **Model** dropdown → pick a model → paste its API key → **Save**. A key already set? Use the **Update {KEY}** expander to replace it.

**Ask** — Type in plain English. You get prose + a chart (+ a comparison table when comparing entities).

**Export a deck** — Export buttons appear when the answer is an *executive brief* — i.e. the question contains **"brief", "summary", "deck", or "board"**, or spans all sources (e.g. *"Give me an executive brief on revenue and customers."*). Two options:
- **📥 .pptx (offline)** — instant, no account needed. Styled 16:9 deck: branded navy title slide, colored header bars, a real rendered bar/line chart, and a sources slide
- **✨ Generate in Gamma** — a polished deck in ~1–2 min; paste a [Gamma](https://gamma.app) API key once (in the deck panel or `secrets.toml`) and it's produced in your Gamma workspace with a shareable link

**Per-source credentials** — Creds can be shared globally (`SNOWFLAKE_PASSWORD`) or scoped to one source (`PROD_DB__SNOWFLAKE_PASSWORD`), so two sources can use different accounts. The bare key is the fallback; the wizard handles this automatically.

---

## Models

Defined in `registry/models.yaml`. Add any OpenAI-compatible provider (Together, Fireworks, OpenRouter, local vLLM/Ollama) by adding a block with `adapter: openai_compatible`, a `base_url`, and an `api_key_env` — **no code changes**. Add the key and it appears in the dropdown.

---

## Evaluation

```bash
uv run python eval.py
```

| Layer | Checks |
|---|---|
| **1 — Output contract** | every response matches the required JSON shape |
| **2 — Calculation** | deterministic known-answer checks from `eval_facts.yaml` (no LLM-as-judge) |
| **3 — Source routing** | the right source is queried per question |

Exits non-zero if Layer 1/3 fail or Layer 2 drops below 95%.

---

## Output contract

```json
{
  "answer": "Plain-English response with figures and attribution.",
  "chart": { "type": "bar|line|none", "title": "", "x": [], "y": [] },
  "slide_deck": false,
  "sources_used": ["source_id"],
  "follow_up_hints": ["...", "..."]
}
```

---

## Deployment

Designed for **[Streamlit Community Cloud](https://streamlit.io/cloud)** (free, native Streamlit hosting):

1. Push to GitHub (done) → on Streamlit Cloud, **New app** → point at `app.py`
2. Add your keys/creds under **App → Settings → Secrets** (same keys as `secrets.toml`)
3. Ensure `uv`/`uvx` availability for MCP servers, or pin the MCP packages in `requirements.txt`

> Streamlit needs a persistent server, so serverless hosts like **Vercel** aren't a fit (Vercel targets Next.js/edge). Render, Railway, or Fly.io also work if you outgrow Community Cloud.

---

## Security & production hardening

Authentication here is intentionally **lightweight (demo-grade)** to stay dependency-free per the spec. **RBAC *enforcement* is already server-side** — a user can only query sources their role allows (gated in `ask()` via `allowed_source_ids`). Before a production / multi-user rollout, harden the **authentication layer**:

| Area | Today (demo) | Recommended for production |
|---|---|---|
| Password hashing | sha256 (fast, unsalted) | **bcrypt / argon2** (salted, slow) |
| Identity | Local `users.yaml` | **Managed IdP** — Streamlit native OIDC (`st.login`) with **Auth0 / Google / Microsoft Entra**, or Supabase/Clerk |
| Sessions | In-memory `session_state` | Signed, expiring cookie / IdP-issued token |
| Abuse protection | None | Rate limiting + account lockout + MFA (via IdP) |
| Transport | local HTTP | HTTPS/TLS (automatic on Streamlit Cloud) |

The role → capability → source mapping (`auth.ROLE_CAPABILITIES`) stays the same; only the sign-in/identity layer changes. The cleanest upgrade is **Streamlit's built-in OIDC with Auth0 or Google**, which offloads passwords, MFA, and sessions to the identity provider while keeping our RBAC on top.

---

<div align="center">

**CXO Copilot · IntelliBridge**
*Don't just learn AI. Apply AI.*

</div>
