# Buyer Lead Intake Agent (AgentMira case study)

You give it one free-text buyer inquiry; it hands back a Lead Brief the realtor can read
before picking up the phone. The brief has a short buyer summary, 3–5 ranked property
matches with the reason each one made the list, a "things to be aware of" section for the
judgment calls and flags, one suggested next action, and a confidence rating.

It's a LangGraph agent, and the whole design rests on one line I drew early: language work
goes to the LLM, everything a realtor trusts to be *correct* stays in deterministic code.

---

## The agent

```
START → ingest → extract → safety → match → compose → persist → END
        clean    LLM        code     code     LLM       code
                 (language)  (guard)  (data)   (language) (gated)
```

| Node | Kind | What it does |
|------|------|----------------|
| **ingest**  | code | normalize the raw inquiry |
| **extract** | LLM | free text → typed `BuyerProfile`: locations, budget + stretch, beds, type, hard must-haves vs. soft nice-to-haves, timeline, buyer type, cash, special needs, emotional context, and vagueness / human-judgment flags |
| **safety**  | code | treats the inquiry strictly as data; detects embedded instructions and PII-exfiltration attempts and records a security flag. It never executes them. |
| **match**   | code / SQL | hard-filters the MLS (location, price ≤ budget/stretch, beds, type, must-have features, availability), then scores and ranks the survivors on soft prefs + status. Refuses vague leads and handles referenced-listing leads. |
| **compose** | LLM | writes the buyer summary and per-property reasons from the matches that were *already computed* |
| **persist** | code | writes `<lead_id>.md` + `<lead_id>.json` (gated, so the API can reuse the same graph without touching disk) |

The LLM runs in exactly two nodes. Matching, ranking, flags, the next action, and the
confidence rating are all deterministic — a model never decides which homes match or which
warnings the realtor sees.

---

## Quick start (no config, runs fully offline)

```bash
pip install -r requirements.txt

# 1) Batch runner — the primary deliverable: writes all 12 briefs to output/briefs/
python -m src.batch

# 2) Live JSON API
uvicorn src.api:app --reload      # http://localhost:8000  (Swagger at /docs)

# 3) Streamlit UI — paste an inquiry, see the brief
streamlit run streamlit_app.py
```

With no API key and no database, it uses a deterministic mock LLM and an in-memory matcher,
so the briefs come out the same every time. To point it at a real model:

```bash
export LLM_PROVIDER=openai     OPENAI_API_KEY=sk-...        # or
export LLM_PROVIDER=anthropic  ANTHROPIC_API_KEY=sk-ant-...
```

Nothing else changes — the providers sit behind one interface (`src/llm/base.py`).

---

## Using Postgres (the "real" data layer)

```bash
docker compose up -d db
python -m src.data_layer.loader            # load the CSV, owner PII included
MATCHER_BACKEND=postgres python -m src.batch
```

Hard-constraint matching then runs as a parameterized SQL query
(`src/data_layer/postgres_repo.py`). The SELECT never lists `owner_name` or `owner_phone`,
so that PII never leaves the database — the protection is structural, not a prompt I'm
hoping the model respects. If Postgres isn't up, the app falls back to the identical
in-memory logic and tells you it did.

Run the whole stack (db + API) with `docker compose up --build`.

---

## Live API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/inquiry` | raw inquiry (website-form shape) → Lead Brief JSON |
| `GET`  | `/health` | runtime info: provider, backend, listings loaded |
| `GET`  | `/docs` | auto-generated Swagger |

`/inquiry`, the Streamlit UI, and the batch runner all call the same `run_agent()` in
`src/agent.py`. There's no second copy of the logic anywhere.

```bash
curl -X POST localhost:8000/inquiry -H 'Content-Type: application/json' \
  -d '{"message":"3BR condo in Brickell under $800k with a gym, must have parking"}'
```

---

## Project layout

```
src/
  config.py                 env-driven settings (safe defaults)
  models.py                 Pydantic contracts (Inquiry, BuyerProfile, PropertyMatch, LeadBrief, AgentState)
  vocab.py                  neighborhoods / types / feature synonyms / known-unmatchable wants
  graph.py                  the LangGraph StateGraph (the agent)
  agent.py                  run_agent() — the single entry point (batch + API + UI)
  render.py                 LeadBrief → phone-readable Markdown
  batch.py                  CLI batch runner (primary deliverable)
  api.py                    FastAPI app (/inquiry, /health, /docs)
  llm/                      base interface + openai / anthropic / mock providers + prompts
  data_layer/               repository interface + postgres + in-memory + scoring + CSV loader
  nodes/                    one module per graph node
streamlit_app.py            the Streamlit UI
sql/schema.sql              listings table (handles studios / blanks / outlier flag)
output/briefs/              the 12 generated briefs (.md + .json) + all_briefs.json
tests/test_matching.py      deterministic tests (no LLM or DB needed)
docker-compose.yml          Postgres (+ optional API)
```

---

## How the messy real data is handled

- **Owner PII** — `ListingRow` has no owner fields and no repo ever SELECTs them, so the LLM never sees them. Structural, not prompt-based.
- **listing_status (~70% Active)** — Pending and Active Under Contract listings are flagged per-property and down-ranked, not hidden. A pending deal can still fall through, and the realtor should know it's there.
- **The $250M outlier** — flagged at load time (`is_price_outlier`) and dropped from matching as a data error.
- **Studios (0 or blank beds)** — normalized to 0 = studio, so a `min_beds` filter excludes them correctly.
- **Blank bathrooms** — left nullable, never fabricated.
- **Non-MLS wants** — some ("ocean view", "boat dock") are real features and get matched; others ("good schools", "near pharmacy", "single-story", "elevator", "city view") aren't in the feed at all and get surfaced honestly under "things to be aware of" instead of quietly faked.
- **Too-vague leads** — no invented matches; the brief recommends a qualifying call.
- **Human-judgment asks** (negotiation, seller motivation) — factual context only, with an explicit escalation to the realtor.
- **Prompt injection** — detected, ignored, and flagged, while the genuine request still gets processed.

---

## Tests

```bash
pytest -q          # 8 deterministic tests: dataset load, outlier exclusion, price/beds/
                   # feature filters, unrealistic-budget → empty, scoring, no-PII, injection
```

## Configuration

Every env var is optional (see `.env.example`): `LLM_PROVIDER`,
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`, `MATCHER_BACKEND`, `DATABASE_URL`, `MLS_CSV_PATH`.

## Deliberately out of scope (described in `draft_writeup.md`)

Redis/arq workers, Slack notifications, and Fly.io/Railway deployment.
