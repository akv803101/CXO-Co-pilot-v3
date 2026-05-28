# CLAUDE.md
> Read this file at the start of every session. It is the single source of truth.

---

## 0. Operating Principles

| Rule | What it means |
|------|---------------|
| **Think Before Coding** | Before touching any file, state: what the task is, which files change, and what the minimal change is |
| **Simplicity First** | The minimal working solution beats the elegant overbuilt one |
| **Surgical Changes** | Touch only the files the task requires. Do not refactor unrelated code |
| **Goal-Driven Execution** | Deliver exactly what was asked. Nothing extra unless explicitly requested |

---

## 1. Variables — Fill These In Before Every Session

Every `{{TOKEN}}` in this file maps to a row here.
Update when the brand or period changes. Data source details live in `sources.yaml` — not here.

| Token | Value | Notes |
|-------|-------|-------|
| `{{BRAND_NAME}}` | | Company or demo brand name |
| `{{BRAND_DESCRIPTION}}` | | One-line company description |
| `{{PERIOD}}` | | Active reporting period e.g. Q1 FY25 |
| `{{CURRENCY_SYMBOL}}` | | e.g. ₹ or $ |
| `{{CURRENCY_SHORTHAND}}` | | e.g. Cr/L or M/K |

Data source credentials go in `.streamlit/secrets.toml`.
Data source structure (tables, columns, capabilities) goes in `registry/sources.yaml`.
Never put source-specific details in this variables table.

---

## 2. Project Identity

| Field | Value |
|-------|-------|
| Product | CXO Copilot |
| Tagline | Ask any business question in plain English. Get answers, charts, and slide decks — instantly. |
| Active brand | `{{BRAND_NAME}}` — `{{BRAND_DESCRIPTION}}` |
| Owner | IntelliBridge |

---

## 3. Current Build State

```
Phase 1 — Live Connectors          ← current phase
  ○  orchestrator.py   Claude API + MCP routing, v2 system prompt
  ○  connectors/mcp_config.py   MCP server config builders (one per source type)
  ○  config.py         secrets loading
  ○  registry/sources.yaml   all active data sources defined
  ○  eval.py           three-layer evaluation script
  ○  Snowflake trial account live with real data
  ○  Both Google Sheets created, shared, accessible to Sheets MCP
  ○  All 5 demo question types verified against live data

Phase 2 — Product
  ○  Login + user accounts
  ○  Role-based access control
  ○  Usage analytics

Phase 3 — GTM
  ○  Consulting pilots
  ○  Self-serve SaaS
```

---

## 4. File Structure

```
CXO-Copilot/
│
├── CLAUDE.md                       ← this file
├── app.py                          ← Streamlit UI: chat, charts, layout only
├── orchestrator.py                 ← Claude API call + source routing only
├── config.py                       ← secrets loading only
├── eval.py                         ← three-layer evaluation script
│
├── connectors/
│   └── mcp_config.py               ← MCP server config builders (one per source type)
│
├── registry/
│   └── sources.yaml                ← ALL active data sources for this company
│
├── requirements.txt
└── .streamlit/secrets.toml         ← credentials only, never committed to git
```

**File ownership rule:** Each file has one job. Never cross-contaminate.

**`sources.yaml` is the single config file for all data sources.**
It defines what sources are active, what type they are, what data they hold, and what their schema looks like.
Credentials are never in this file — they stay in `secrets.toml`.

`sources.yaml` format:
```yaml
sources:
  - id: revenue_db              # unique ID used in sources_used[] in API responses
    type: snowflake             # snowflake | bigquery | postgres | mysql | gsheets | csv | rest_api
    label: "Revenue & Forecasts"
    capability: revenue         # what kind of business questions this source answers
    active: true                # set false to disable without deleting
    schema_discovery: both        # mcp | manual | both — use 'both' for accuracy (default)
    connection:
      database: ""              # Snowflake database name — fill in here or reference secrets.toml
      schema: ""                # Snowflake schema name
    tables:
      - name: orders            # actual table/sheet name in the source
        description: "One row per order — revenue, units, region, channel, date"
        columns:
          - name: date          # actual column name
            type: date
            description: "Order date"
          - name: region
            type: string
            description: "Geographic region"
          - name: revenue
            type: number
            description: "Revenue in {{CURRENCY_SYMBOL}}"
      - name: forecast
        description: "Period-level targets by region"
        columns:
          - name: period
            type: string
            description: "Reporting period"
          - name: region
            type: string
          - name: target_revenue
            type: number

  - id: pipeline_sheet
    type: gsheets
    label: "Pipeline / CRM"
    capability: pipeline
    active: true
    schema_discovery: both       # MCP reads headers, config annotates with descriptions
    sheet_id: ""                 # fill in from secrets.toml or directly here
    tables:
      - name: Pipeline           # sheet tab name
        description: "One row per deal"
        columns:
          - name: deal_name
          - name: stage
          - name: value
          - name: close_date
          - name: region
          - name: owner
          - name: risk_flag

  - id: campaigns_sheet
    type: gsheets
    label: "Marketing Campaigns"
    capability: campaigns
    active: true
    schema_discovery: both
    sheet_id: ""
    tables:
      - name: Campaigns
        description: "One row per campaign per channel"
        columns:
          - name: campaign_name
          - name: channel
          - name: spend
          - name: revenue_attributed
          - name: period
```

**Adding a new data source:** add a new entry to `sources.yaml`, set `active: true`, and add its credentials to `secrets.toml`. No other file changes needed.

**Supported source types and their MCP servers:**

| Type | MCP server | Notes |
|------|-----------|-------|
| `snowflake` | `uvx snowflake-mcp` | SQL queries via Snowflake MCP |
| `bigquery` | `uvx mcp-bigquery` | SQL queries via BigQuery MCP |
| `postgres` | `uvx mcp-postgres` | SQL queries via Postgres MCP |
| `mysql` | `uvx mcp-mysql` | SQL queries via MySQL MCP |
| `gsheets` | `uvx mcp-google-sheets` | Read/write Google Sheets |
| `csv` | built-in tool | Local file, no MCP needed |
| `rest_api` | custom tool | Define endpoint + auth in sources.yaml |

---

## 5. Data Sources

All data comes through MCP or built-in tools. There is no mock data, no hardcoded fallback.
**The active set of sources is defined entirely in `registry/sources.yaml`.**

### How Claude learns the schema

Schema discovery follows the `schema_discovery` field per source in `sources.yaml`:

| Mode | Behaviour |
|------|-----------|
| `mcp` | Claude asks the MCP server for schema at query time — fully dynamic |
| `manual` | Claude reads column definitions from `sources.yaml` only — fastest, most accurate |
| `both` | MCP discovers schema, `sources.yaml` annotations take priority when they conflict — **use this for accuracy** |

**Default for all sources: `both`.** The config file is the source of truth. MCP fills gaps.

### Current active sources (Snowflake default)

Source type is `snowflake`. Two other sources are `gsheets`.
All three are defined in `sources.yaml`. To swap Snowflake for BigQuery or Postgres — change `type` in `sources.yaml` and add credentials to `secrets.toml`. No code changes needed.

### Schema rules

- Column names in `sources.yaml` must match the real source exactly — Claude uses them verbatim in queries
- If a column is renamed in the source, update `sources.yaml` first, then run `eval.py`
- `description` fields in `sources.yaml` are injected into the orchestrator system prompt so Claude understands what each column means
- ROI and other derived metrics are never stored — Claude computes them from raw columns at query time

---

## 6. Demo Question Types

These five question types must all return correct answers.
Exact numbers come from live `{{BRAND_NAME}}` data — not asserted here.
The output shape is fixed — Claude Code must match this structure exactly.

| # | Type | Sources | What it tests |
|---|------|---------|---------------|
| Q1 | Revenue vs forecast | Snowflake | Actuals vs target, variance %, regional breakdown |
| Q2 | Campaign ROI | Sheets — campaigns | ROI calc from raw spend + revenue, chart output |
| Q3 | Pipeline health | Sheets — pipeline | Stage reasoning, natural-language risk summary |
| Q4 | Executive brief | Snowflake + Sheets — pipeline + Sheets — campaigns | Full federation + slide deck export trigger |
| Q5 | Drill-down follow-up | Snowflake | Conversation memory, multi-turn, single-source re-query |

**Q4 is the slide deck trigger.**
**Q5 requires full conversation history in the API call. "You said" is the signal.**

**Expected output shape for every question (no exceptions):**

```
{
  "answer":          "Plain-English response with figures, % change, and attribution.",
  "chart": {
    "type":          "bar" | "line" | "none",
    "title":         "Chart title",
    "x":             ["label1", "label2"],
    "y":             [value1, value2]
  },
  "slide_deck":      true | false,
  "sources_used":    ["snowflake", "gsheets_pipeline", "gsheets_campaigns"],  ← include only sources actually queried
  "follow_up_hints": ["Follow-up question 1", "Follow-up question 2"]
}
```

**Example — Q1 shape (values are illustrative, not hardcoded):**

Input: "Did we hit our `{{PERIOD}}` revenue target? Where did we miss?"

```
{
  "answer":          "{{BRAND_NAME}} missed the {{PERIOD}} target by X {{CURRENCY_SHORTHAND}} (–Y%). 
                      The [region] region drove the largest gap at –Z%.",
  "chart": {
    "type":          "bar",
    "title":         "{{PERIOD}} Actuals vs Target by Region",
    "x":             ["Region A", "Region B", "Region C"],
    "y":             [actual1, actual2, actual3]
  },
  "slide_deck":      false,
  "sources_used":    ["snowflake"],
  "follow_up_hints": ["What drove the miss in [region]?", 
                      "How does this compare to the previous period?"]
}
```

---

## 7. Orchestrator Instructions

When building or updating `orchestrator.py`:

**At startup, load `sources.yaml` and build the system prompt dynamically.**
The orchestrator reads all active sources from `sources.yaml` and injects them into the system prompt at runtime. No source names, table names, or column names are hardcoded in the orchestrator.

**MCP servers to register:**
Read `sources.yaml` at startup. For each active source, spin up its MCP server based on `type`.
The `mcp_config.py` function takes a source entry from `sources.yaml` and returns the correct MCP server config.
Use `client.beta.messages.create` with `betas=["mcp-client-2025-04-04"]`.

**System prompt must be built dynamically and must include:**
- For each active source: its `label`, `capability`, table names, and column descriptions — all read from `sources.yaml`
- Active period `{{PERIOD}}`, brand `{{BRAND_NAME}}`, currency `{{CURRENCY_SYMBOL}}` + `{{CURRENCY_SHORTHAND}}` injected at runtime
- Routing rules: built from the `capability` field per source in `sources.yaml` — not hardcoded. Example: `capability: revenue` → route revenue questions to this source
- Output format: JSON with keys `answer`, `chart`, `slide_deck`, `sources_used`, `follow_up_hints`
- Slide deck trigger: any question spanning all active sources, or containing "brief", "summary", "deck", "board"
- Tone: direct, no filler, end every answer with 2 follow-up questions

**Routing rule (source-agnostic):**
Claude routes questions by matching the question intent to the `capability` field of each source in `sources.yaml`.
When a new source is added to `sources.yaml`, routing adapts automatically — no orchestrator code changes needed.

| Capability value | Routes questions about |
|-----------------|----------------------|
| `revenue` | actuals, targets, variance, regional breakdown |
| `pipeline` | deals, stages, ARR, close dates, risk |
| `campaigns` | spend, ROI, channel performance, attribution |
| `hr` | headcount, attrition, hiring |
| `finance` | P&L, burn rate, cost centres |
| (any new value) | described in the source's `description` field |

**Calculation rules:**
- MCP tools return raw rows — Claude does all math itself
- Claude infers which metric to compute from the question — no formulas hardcoded
- Complete all arithmetic before writing the answer
- Show formula logic in plain English so the exec can verify e.g. "ROI = `{{CURRENCY_SYMBOL}}`X revenue ÷ `{{CURRENCY_SYMBOL}}`Y spend = Z×"
- Never approximate prematurely — round only in the final displayed figure
- Derive unknown metrics from first principles — never refuse

**Chart rules:**
- Bar — category comparisons
- Line — time series
- None — pure narrative answers only
- Chart values must match the answer numbers exactly

**Multi-turn rule:**
- Full conversation history in every API call
- On "you said" / "that region" / "the campaign" — extract entity from prior message, re-query only the needed source

---

## 8. Session Start Checklist

- [ ] Variables table in Section 1 is filled in
- [ ] `registry/sources.yaml` has at least one active source with correct column names
- [ ] All active sources have credentials in `secrets.toml`
- [ ] State which file(s) this task will touch before editing anything
- [ ] After any change, run `python eval.py` — all three layers must pass before marking anything ✓

---

## 9. Conventions

| Topic | Rule |
|-------|------|
| Currency | Always `{{CURRENCY_SYMBOL}}` + `{{CURRENCY_SHORTHAND}}` — never raw numbers without unit |
| Secrets | All keys in `.streamlit/secrets.toml` only, loaded via `config.py` — never hardcoded |
| Error handling | If an MCP source fails, return a partial answer from the other sources and flag the gap explicitly — never crash silently. Failure response must follow this shape: `{"answer": "Could not reach [source]. Here is what the other sources show: ...", "chart": {"type": "none"}, "slide_deck": false, "sources_used": ["source_that_worked"], "follow_up_hints": []}` |
| MCP beta stability | `betas=["mcp-client-2025-04-04"]` is an Anthropic beta flag — behaviour can change without notice. Always run `eval.py` the night before any demo or client presentation. Never demo from a cold start. If the beta flag changes, update it in `mcp_config.py` only — one place, one change |
| Git | `secrets.toml` and `.env` always in `.gitignore` |
| Extra output | Deliver only what was asked. No extra files, helpers, or refactors unless explicitly requested |

---

## 10. Connector Setup — Do This When Ready

Code is written and waiting. Complete these steps when you are ready to connect live data.
Nothing here needs to be done before the code is built.

**General pattern for any new source:**
1. Add a source entry to `registry/sources.yaml` with `active: true`
2. Add credentials to `.streamlit/secrets.toml`
3. Run `uvx <mcp-server-for-type>` once to install
4. Run `python eval.py` to verify

---

### Snowflake (current default)

**Step 1 — Create a trial account**
Go to snowflake.com → Start for Free → sign up.
Note account identifier, username, password → go into `secrets.toml`.

**Step 2 — Create database and schema**
Choose any names. Set them in the `connection.database` and `connection.schema` fields of the Snowflake entry in `sources.yaml`.

**Step 3 — Create tables**
Create an orders table (date, region, channel, revenue, units) and a forecast table (period, region, target_revenue).
Update the `tables` block in `sources.yaml` to match exact column names.

**Step 4 — Load data**
Upload any CSV or use Snowflake's load wizard. 50 rows minimum to test.

**Step 5 — Install MCP server**
```
uvx snowflake-mcp
```
uvx auto-installs on first run.

**Step 6 — Add to secrets.toml**
```
SNOWFLAKE_ACCOUNT    = your account identifier
SNOWFLAKE_USER       = your username
SNOWFLAKE_PASSWORD   = your password
SNOWFLAKE_WAREHOUSE  = COMPUTE_WH
```
COMPUTE_WH is the Snowflake trial default. Update if different.

---

### Google Sheets

**Step 1 — Create sheets**
One sheet per data domain (pipeline, campaigns, etc.). Column names are flexible — update `sources.yaml` to match.

**Step 2 — Get Sheet IDs**
URL between `/d/` and `/edit`. Add to the `sheet_id` field in `sources.yaml` or `secrets.toml`.

**Step 3 — Install MCP server**
```
uvx mcp-google-sheets
```
Verify package name at: github.com/modelcontextprotocol/servers

**Step 4 — Authenticate**
Google OAuth flow or service account JSON. Store credential path in `secrets.toml`.

---

### Adding any other source type (BigQuery, Postgres, MySQL, CSV, REST API)

**Step 1 — Add entry to `sources.yaml`**
Set `type` to the correct value, `active: true`, fill in `tables` and `columns`.

**Step 2 — Add credentials to `secrets.toml`**
Key names follow the pattern: `<SOURCE_ID>_<CREDENTIAL>` e.g. `BQ_PROJECT_ID`, `PG_PASSWORD`.

**Step 3 — Install the MCP server for that type**

| Type | Command |
|------|---------|
| BigQuery | `uvx mcp-bigquery` |
| PostgreSQL | `uvx mcp-postgres` |
| MySQL | `uvx mcp-mysql` |
| CSV | no install — built-in tool |
| REST API | define endpoint + auth in `sources.yaml` under `rest_config` |

**Step 4 — Verify**
Run `python eval.py`. Layer 3 routing checks will confirm the new source is reachable and routing correctly.

---

### Final check before first run

- [ ] All intended sources have `active: true` in `sources.yaml`
- [ ] `sources.yaml` column names match the real source exactly
- [ ] `secrets.toml` has credentials for every active source
- [ ] MCP server for each active source starts cleanly in terminal
- [ ] Variables table in Section 1 is fully filled in
- [ ] Run `python eval.py` — all three layers pass

---

## 11. Evaluation Strategy

Run `python eval.py` before every commit. Three layers — all must pass before any phase is marked ✓.

---

### Layer 1 — Output Contract (run always)

Every response must match the JSON shape defined in Section 6.
These are structural checks — no data required, just validate the response.

| Check | Assertion |
|-------|-----------|
| Required keys present | `answer`, `chart`, `slide_deck`, `sources_used`, `follow_up_hints` all exist |
| Chart type valid | `chart.type` is one of `bar`, `line`, `none` |
| Chart data aligned | `chart.x` and `chart.y` are same length when type is not `none` |
| Sources non-empty | `sources_used` is a list with at least one item |
| Follow-ups present | `follow_up_hints` has exactly 2 items |
| Slide deck is boolean | `slide_deck` is `true` or `false`, never null or string |

Pass target: 100%. A single failure here means the app crashes before the exec reads anything.

---

### Layer 2 — Calculation Accuracy (run against fixed test data)

Seed a separate test schema in the active revenue source and add EVAL tabs to your existing Google Sheets for fixed rows where you know the correct answer. Ask Q1–Q5 against this fixed data. Assert the figures in the response match your manually calculated values.

**Test data requirements:**
- Revenue source: create an `EVAL` schema (SQL sources) or `EVAL` tab (sheet sources) — separate from production data
- Fixed rows with round numbers so manual verification is unambiguous
- At least one region that over-performs and one that under-performs
- At least two campaigns with clearly different spend-to-revenue ratios so computed ROI is unambiguous
- At least two pipeline deals with different stages and risk flags

**Assertions per question type:**

| Question | Assert |
|----------|--------|
| Q1 — Revenue vs forecast | Variance figure and % match manual calculation exactly |
| Q2 — Campaign ROI | ROI per channel matches `revenue_attributed ÷ spend` for each row |
| Q3 — Pipeline health | At-risk deal count matches rows where `risk_flag = true` |
| Q4 — Executive brief | `slide_deck` is `true`, all three sources appear in `sources_used` |
| Q5 — Drill-down | Answer references the same region as Q1 response without re-asking context |

Pass target: 95%+. The 5% margin covers rounding at the last decimal place only.

**Do not use LLM-as-judge for numerical accuracy.** Claude grading Claude's own math carries the same errors you are trying to catch. Use deterministic string and number matching only.

---

### Layer 3 — Source Routing (run always)

Does Claude query the right source for each question type?
Check `sources_used` in the response — wrong routing means wrong data even if the math is correct.

Routing assertions are derived from `sources.yaml` at eval time, not hardcoded here.
For each active source, assert: questions matching its `capability` include its `id` in `sources_used`.

| Capability | Must include source with this capability |
|-----------|----------------------------------------|
| `revenue` | the revenue source id |
| `pipeline` | the pipeline source id |
| `campaigns` | the campaigns source id |
| executive brief | all active source ids |
| drill-down follow-up | only the source needed for the specific entity |

Note: multi-intent questions may correctly include more than one source. Assert minimum required sources, not maximum.

Pass target: 100%. No exceptions.

---

### eval.py instructions for Claude Code

When building `eval.py`:
- Read `registry/sources.yaml` at startup to discover active sources and their IDs
- For each active source, seed an EVAL dataset before running:
  - SQL sources (snowflake, bigquery, postgres, mysql): create an `EVAL` schema with the same table structure as production — 10 rows minimum, round numbers, known SUM per region
  - Sheet sources (gsheets): add an `EVAL` tab to each active sheet — same columns as production
  - CSV sources: use a separate `data/eval/` folder
- Forecast / target data: 1 row per region for `{{PERIOD}}` — one region above target, one below, exact round numbers
- Pipeline EVAL data: 4 deals — 2 stages, 1 with risk_flag=true, 1 false
- Campaigns EVAL data: 3 campaigns — clearly different spend and revenue_attributed so ROI is unambiguous
- Run all 5 question types sequentially, passing conversation history for Q5
- Run all three layers against each response
- Print a structured report: layer name, question, pass/fail, failure reason if any
- Exit with code 1 if any Layer 1 or Layer 3 check fails
- Exit with code 1 if Layer 2 pass rate drops below 95%
- Never modify production data — eval reads and writes to EVAL datasets only

---

## 12. UI & User Flow

This section is the complete spec for `app.py`. Build exactly this — nothing more.

---

### Screen 1 — Login

- Simple login screen, centred
- Email + password fields
- No social login, no SSO for now
- On success → Screen 2

---

### Screen 2 — Onboarding Canvas (no sources connected yet)

- Full canvas, clean and empty
- Centre: a `+` icon with label "Connect a data source"
- Clicking `+` opens the Connection Wizard (see below)
- Left sidebar visible but inactive until at least one source is connected

---

### Connection Wizard (modal/drawer)

Triggered by `+` icon or "Add Data Source" in sidebar. Steps:

**Step 1 — Choose source type**
Dropdown options (maps to `type` in sources.yaml):
- Snowflake
- Google Sheets
- BigQuery
- PostgreSQL / MySQL
- CSV / Excel Upload
- REST API

**Step 2 — Enter credentials**
Fields rendered dynamically based on source type selected.
Credentials written to `secrets.toml` only — never stored in UI state.

**Step 3 — Set domain**
Dropdown — what kind of business data does this source hold?

| Option shown to user | `capability` value written to sources.yaml |
|---------------------|------------------------------------------|
| Revenue & Sales | `revenue` |
| Pipeline & CRM | `pipeline` |
| Marketing & Campaigns | `campaigns` |
| Finance & P&L | `finance` |
| HR & People | `hr` |
| Other | `custom` |

Multiple domains allowed per source — user can select more than one.

**Step 4 — Name this source**
Free text — becomes the `label` field in sources.yaml.

**Step 5 — Connect**
On submit:
1. Write source entry to `registry/sources.yaml` with `active: true`
2. Write credentials to `secrets.toml`
3. Call `on_source_connected(source_id)` — see Section 13
4. On success → transition to Screen 3

---

### Screen 3 — Main App (sources connected)

**Left sidebar — always visible:**

| Item | Action |
|------|--------|
| Home | Returns to canvas overview |
| New Chat | Opens a fresh chat window, clears conversation history |
| Add Data Source | Opens Connection Wizard |
| Connected Sources | Expandable list of active sources from sources.yaml — click to view schema |

**Main area — Chat window:**

- Appears after first source is connected
- Top of chat: 3 suggested questions auto-generated by `on_source_connected()` shown as clickable chips — clicking one sends it as the first message
- Chat input at bottom — single text box, plain English
- Send button + Enter key both submit

**Response rendering — based on JSON output from orchestrator:**

| Field | How it renders |
|-------|---------------|
| `answer` | Text block — clean, readable prose |
| `chart.type: bar` | Inline bar chart below the answer |
| `chart.type: line` | Inline line chart below the answer |
| `chart.type: none` | No chart rendered |
| `slide_deck: true` | "Export as Deck" button appears — clicking calls Gamma export |
| `follow_up_hints` | Two clickable chips below the response — clicking sends as next message |
| `sources_used` | Small source badges shown at bottom of response |

**Comparison responses:**
When the answer compares two or more entities (regions, campaigns, channels), render a side-by-side comparison table above the chart.

---

### Screen states summary

```
Login → Canvas (+) → Connection Wizard → Chat window
                           ↑
                    sidebar: Add Data Source (anytime)
```

---

## 13. New Backend Functions

Two functions must be added to `orchestrator.py`. These are the only additions to the backend spec — nothing else changes.

---

### Function 1 — `on_source_connected(source_id: str) -> dict`

**Triggered:** immediately after a new source is written to sources.yaml via the Connection Wizard.

**What it does:**
1. Reads the new source entry from sources.yaml
2. Calls the source's MCP server to fetch a sample of data (first 20 rows or equivalent)
3. Passes sample to Claude with this instruction: "You have just been connected to a new data source. Read the sample, understand what it contains, and generate exactly 3 suggested questions a business executive would want to ask about this data. Return JSON only."
4. Returns structured response:
```
{
  "source_label": "Revenue & Forecasts",
  "summary": "One sentence describing what this source contains",
  "suggested_questions": [
    "Question 1",
    "Question 2",
    "Question 3"
  ]
}
```

**Rules:**
- Suggested questions must be specific to the actual data seen — not generic
- If sample fetch fails, return 3 generic questions based on the `capability` field only
- This function does not add to conversation history

---

### Function 2 — `set_source_domain(source_id: str, capability: list[str]) -> bool`

**Triggered:** when user selects domain(s) in Step 3 of the Connection Wizard.

**What it does:**
1. Reads `registry/sources.yaml`
2. Finds the entry with matching `id`
3. Updates its `capability` field with the provided list
4. Writes the file back
5. Returns `True` on success, `False` on failure

**Rules:**
- Only modifies the `capability` field — nothing else in the entry
- If source_id is not found, raise a clear error — do not create a new entry
- File write must be atomic — read full yaml, modify in memory, write full yaml back

---

## 14. Locked Scope

**This is the complete spec. Nothing outside this document gets built.**

| In scope | Out of scope |
|----------|-------------|
| All of Sections 0–13 | User roles / permissions |
| Snowflake + Google Sheets as primary sources | Real-time data streaming |
| Login (email + password) | SSO / OAuth login |
| Connection Wizard for all source types | Automated schema migration |
| Chat with text + chart + comparison + slides | Mobile app |
| `on_source_connected` suggested questions | Scheduled reports / alerts |
| `set_source_domain` capability update | Multi-tenant isolation |
| eval.py three-layer testing | Billing / usage tracking |

If a task or feature is not listed in the In Scope column — stop and flag it before building.

---
*CXO Copilot · CLAUDE.md · IntelliBridge — Don't just learn AI. Apply AI.*
