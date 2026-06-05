# CXO Copilot

**Ask any business question in plain English. Get answers, charts, and slide decks — instantly.**

CXO Copilot connects to your live data sources (Snowflake, Google Sheets, Postgres, MySQL, BigQuery) and lets executives ask questions in natural language. It routes each question to the right source, runs the queries through MCP, does the math, and returns a structured answer with charts, comparison tables, and exportable decks — powered by the LLM of your choice (Anthropic, OpenAI, Groq, or any OpenAI-compatible provider).

Built by **IntelliBridge**. The full product spec lives in [`CLAUDE.md`](./CLAUDE.md).

---

## Highlights

- 🔌 **Live data via MCP** — no mock data; queries run against your real sources
- 🧠 **Multi-model** — Anthropic, OpenAI, Groq, and any OpenAI-compatible provider; switch per chat
- 🗂 **Source-agnostic** — all sources defined in one `registry/sources.yaml`; add/edit/remove from the UI
- 📊 **Rich answers** — prose + bar/line charts + comparison tables + `.pptx` deck export
- 🔁 **Multi-source federation** — query across sources in one question; a failing source is skipped, not fatal
- 🔐 **Credentials in the UI** — enter API keys and source creds in-app; never hardcoded, never in git
- 📈 **Usage analytics** — per-query log with model/source/user breakdowns
- ✅ **Three-layer eval** — output contract, calculation accuracy, source routing

---

## Architecture

```
app.py            Streamlit UI — login, connection wizard, chat, charts, usage
orchestrator.py   Builds the system prompt from sources.yaml, runs the tool-call loop,
                  on_source_connected / set_source_domain / add_source / remove_source
llm/              Provider-agnostic LLM layer
  base.py           one chat() contract (text + tool calls)
  anthropic_provider.py    native Claude adapter
  openai_provider.py       OpenAI-compatible (OpenAI, Groq, Together, Fireworks, local)
mcp_host.py       Synchronous stdio MCP client — spawns each source's server,
                  discovers tools, runs the provider-agnostic tool loop
connectors/
  mcp_config.py     MCP server config builder per source type
config.py         Secrets loading (global + per-source) — reads fresh each call
analytics.py      Append-only usage log + summaries
slides.py         Offline .pptx deck export
eval.py           Three-layer evaluation
registry/
  sources.yaml      single source of truth for all data sources (no credentials)
  models.yaml       pluggable LLM provider/model registry
  eval_facts.yaml   known-answer checks for eval Layer 2
.streamlit/
  secrets.toml      credentials (gitignored)
  users.yaml        app login users (gitignored)
```

**Design rule:** each file has one job. Credentials live only in `.streamlit/secrets.toml`; source structure lives only in `registry/sources.yaml`.

---

## Setup

Requires Python ≥ 3.10 and [`uv`](https://github.com/astral-sh/uv) (for the `uvx` MCP servers).

```bash
git clone https://github.com/akv803101/CXO-Co-pilot-v3.git
cd CXO-Co-pilot-v3

# create a venv and install deps
uv venv --python 3.12
uv pip install -r requirements.txt

# configure
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your keys/creds
cp .streamlit/users.yaml.example  .streamlit/users.yaml      # app login users
```

### Run

```bash
uv run streamlit run app.py
# open http://localhost:8501
```

Demo logins (from `users.yaml.example`): `admin@demo.co` / `admin123`.

---

## Connecting a data source

Everything is doable in the UI — no file editing required.

1. **Sidebar → Add Data Source** → pick a type (Snowflake, Google Sheets, BigQuery, Postgres/MySQL, CSV, REST API)
2. Enter credentials (written to `secrets.toml` only), the database/schema, and the tables/views to expose
3. Pick the business domain(s) and name the source → **Connect**

Use **✏️ Edit** to view/fix a source's saved values, **🗑 Remove** to delete it. Adding an LLM key: pick a model in the sidebar, paste the key, **Save**.

### Per-source credentials

Credentials can be shared globally (e.g. `SNOWFLAKE_PASSWORD`) or scoped to one source by prefixing the source id (`PROD_DB__SNOWFLAKE_PASSWORD`). This lets two sources use different accounts. The bare key is the fallback. The wizard/Edit screens handle this automatically.

---

## Models

Available models are defined in `registry/models.yaml`. Add any OpenAI-compatible
provider (Together, Fireworks, OpenRouter, a local vLLM/Ollama server) by adding a
block with `adapter: openai_compatible`, a `base_url`, and an `api_key_env` — no code
changes. Add the matching key in `secrets.toml` (or via the sidebar) and it appears
in the dropdown.

---

## Evaluation

```bash
uv run python eval.py
```

- **Layer 1 — Output contract:** every response matches the required JSON shape
- **Layer 2 — Calculation accuracy:** deterministic known-answer checks from `registry/eval_facts.yaml` (no LLM-as-judge)
- **Layer 3 — Source routing:** the right source is queried for each question

Exits non-zero if Layer 1/3 fail or Layer 2 drops below 95%.

---

## Output contract

Every answer is returned as:

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

*CXO Copilot · IntelliBridge — Don't just learn AI. Apply AI.*
