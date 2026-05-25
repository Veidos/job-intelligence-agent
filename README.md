# Job Intelligence Agent

> Personal career intelligence system for the Spanish job market.  
> Scrapes InfoJobs, scores offers against your CV using a local LLM, and delivers ranked recommendations to Telegram — fully offline-first.

![Python](https://img.shields.io/badge/Python-3.14+-blue?logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-gemma4:e4b-black?logo=ollama)
![SQLite](https://img.shields.io/badge/SQLite-WAL%20mode-003B57?logo=sqlite)
![Tests](https://img.shields.io/badge/Tests-171%20passing-brightgreen)
![License](https://img.shields.io/badge/License-MIT-green)
![Cost](https://img.shields.io/badge/Cost-~$2.70%2Fmonth-lightgrey)

---

## What it does

| Step | Module | Description |
|------|--------|-------------|
| **1. Scrape** | `fetch.py` | Pulls fresh offers from InfoJobs via Apify daily |
| **2. Enrich** | `fetch.py` | Extracts skills, seniority and salary with a local LLM (no cloud) |
| **3. Score** | `evaluate.py` | Deterministic formula matches each offer to your CV profile |
| **4. Deliver** | `send.py` | Top 3 ranked offers sent to Telegram every morning |

```mermaid
flowchart TD
    A[InfoJobs via Apify] --> B[fetch.py]
    B --> C[(SQLite\noffers)]
    C --> D[role_classifier.py]
    D --> E[evaluate.py]
    E --> F[gemma4:e4b\nTechnical + HR]
    F --> G[match_score]
    G --> H[send.py]
    H --> I[📱 Telegram]
    K[fetch_company.py] --> L[(SQLite\ncompanies)]
    L --> E
    I --> M[💬 User Feedback\n/f1 /f2 /f3 /dia]
    M --> N[(user_psychology\nevolutive memory)]
```

> **⚠️ Architecture note (pending ADR-009):** The `role_classifier` step is a candidate for removal — its `relevance_flag` output is largely redundant with the score produced by `evaluate.py`. Tracked for the next refactor.

---

## Scoring System

Deterministic 0–1 score. Python computes everything — the LLM contributes only one component (`F_fit`, weight 0.15).

### Formula

```
S = 0.45·M_core + 0.15·M_sec + 0.25·F_exp + 0.15·F_fit
```

| Weight | Variable | What it measures | Computed by |
|--------|----------|------------------|-------------|
| 0.45 | `M_core` | Average level match over core skills | Python |
| 0.15 | `M_sec` | Average level match over secondary skills | Python |
| 0.25 | `F_exp` | Years of experience, penalised by employment gap | Python |
| 0.15 | `F_fit` | Cultural fit, location, work mode | gemma4:e4b |

---

### Skills: level multiplier

For each skill in the offer, a multiplier `L_i` is computed:

```
L_i = min(ord(candidate_level), ord(required_level)) / ord(required_level)
```

If the offer does not specify a per-skill level, it is inferred from the job's seniority label. The ordinal is the numeric rank used in the formula:

| Seniority label | Inferred level | Ordinal |
|-----------------|----------------|---------|
| `junior` | basic | 1 |
| `mid` | intermediate | 2 |
| `senior` | advanced | 3 |

- Candidate lacks the skill → `L_i = 0`
- Overqualification capped at `1.0`
- `M_core = avg(L_i)` over core skills · `M_sec = avg(L_i)` over secondary skills

---

### Experience: gap penalty

```
F_exp = years_match × G(gap)

years_match = 1.0                                       if experience_min = 0
years_match = min(candidate_years / experience_min, 1.0)  otherwise
```

`G(gap)` is a multiplier that reduces `F_exp` based on how long the candidate has been out of work. It applies on top of `years_match` — not on the final score:

| Gap (years) | G multiplier | Max F_exp contribution to S |
|-------------|--------------|------------------------------|
| < 1 | 1.00 | 0.25 |
| 1 – 2 | 0.85 | 0.21 |
| 2 – 3 | 0.70 | 0.18 |
| 3 – 4 | 0.55 | 0.14 |
| ≥ 4 | 0.40 | 0.10 |

> Even with a 4+ year gap, strong skill scores can still produce a result above the 0.35 delivery threshold. The gap penalises `F_exp` only — not the full score.

---

### Context fit

`F_fit` is the only LLM-driven component. gemma4:e4b (temperature 0.0) evaluates context fit (0–1) considering cultural compatibility, location, work mode, and personal profile. Skills and gap are already captured by the other components and must **not** be part of this evaluation.

---

### Rating thresholds

| Score | Label | Action |
|-------|-------|--------|
| 0.75 – 1.00 | **Priority** | Apply immediately |
| 0.55 – 0.75 | **Apply** | Strong candidate |
| 0.35 – 0.55 | **Low expectations** | Sent with note |
| 0.00 – 0.35 | **Skip** | Not delivered |

Top 3 offers with score ≥ 0.35 delivered daily. If none qualify: `"No relevant offers today."`

> Full technical reference in [`docs/RATING.md`](docs/RATING.md).

---

## Role Classification

Before scoring, each offer is classified by its **actual requirements** — not its job title. A "Data Scientist" posting that only requires SQL and Excel is classified as `bi_analyst`. A "Data Analyst" posting requiring PyTorch and MLOps is classified as `ml_engineer`.

The classifier maintains a dynamic catalog of canonical role names (in `snake_case`). New roles are detected deterministically (`role_normalized not in catalog`) and added automatically.

Each offer receives a `relevance_flag` and a `gap_type`:

| Flag | Meaning |
|------|---------|
| `core` | Requirements match >70% of candidate profile |
| `adjacent` | 40–70% match, manageable gap (tool/domain) |
| `stretch` | 20–40% match, significant learning required (seniority) |
| `temporal` | Viable bridge job while searching |

### Design principles (ADR-005)

The classifier follows four rules established after 6 iterations (v1–v6):

1. **Model reasons, Python decides** — `is_new_role`, `gap_type` resolution, JSON validation live in code, not the prompt
2. **Atomic prompt changes** — never bundle a parsing fix with a prompt restructure
3. **Separated decision axes** — PHASE 1 (role objective) vs PHASE 2 (candidate fit) are never mixed
4. **Traceability always** — every computed field is persisted to DB

See [`docs/adr/005-classifier-evolucion-v1-a-v6.md`](docs/adr/005-classifier-evolucion-v1-a-v6.md) for the full evolution and validation tables.

---

## Feedback System

After each daily Telegram message, you can optionally reply:

```
/f1 I don't see myself in a marketing company
/f2 interesting, but it seems like a very large company
/f3 good offer
/dia I don't have the energy to apply to anything today
```

The bot replies `"Noted 📝"` or `"Got it, I'll keep that in mind 🧠"`. Feedback is **never used to filter offers**. Instead, gemma4:e4b uses it to add personalized notes to future evaluations:

> *"I know large companies aren't your thing, but this offer is a great technical match for your profile."*

A weekly process compresses accumulated feedback into a psychological summary (`user_psychology` table), which evolves over time without growing infinitely.

---

## Intelligence Layer (Phase 4)

The system accumulates data over time to surface strategic signals:

- **Role Discovery** — finds reachable roles with skill overlap, even outside initial search queries
- **Market Signals** — weekly trends: volume, competition, salary, remote %, emerging skills
- **Strategic Advisor** — auto-triggers advice when patterns are detected (cold market, recurring skill gap, low avg score)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.14+ |
| Database | SQLite (WAL mode) |
| ORM | SQLAlchemy 2.0 |
| Local LLM | Ollama (`gemma4:e4b`) |
| Job data source | Apify — InfoJobs Spain Jobs Scraper |
| Notifications | Telegram Bot API |
| Linting | Ruff |
| Scheduling | cron |

---

## Project Structure

```
job-intelligence-agent/
├── AGENTS.md              ← AI agent context (read by OpenCode)
├── PERFIL.md              ← Candidate source of truth (gitignored)
├── PLANS.md               ← Project ledger (phases + task status)
├── MEMORIES.md            ← Accumulated system learnings
├── requirements.txt
├── .env                   ← Credentials (never commit)
│
├── assets/
│   └── cv.pdf
│
├── docs/
│   ├── adr/               ← Architecture Decision Records
│   ├── CONVENTIONS.md
│   ├── DATABASE.md
│   ├── PIPELINE.md
│   ├── RATING.md
│   ├── TESTING.md          ← Pipeline integration checklist (🤖/👤)
│   └── SETUP.md
│
├── src/
│   ├── db/
│   │   ├── init_db.py     ← Schema initializer + migration runner
│   │   ├── migrate.py     ← Column migrations (ALTER TABLE)
│   │   ├── schema.sql     ← Single source of truth for DB structure
│   │   └── models.py      ← SQLAlchemy models + helpers
│   │
│   ├── onboarding/
│   │   ├── run.py         ← Orchestrates full onboarding
│   │   ├── cv_extractor.py← gemma4:e4b extracts structured data from CV
│   │   └── interviewer.py ← gemma4:e4b conducts guided interview
│   │
│   ├── pipeline/
│   │   ├── run.py         ← Full pipeline orchestrator + CV freshness check
│   │   ├── fetch.py       ← Apify → upsert_raw + enrich_pending
│   │   ├── role_classifier.py ← Classifies offers by real role + relevance
│   │   ├── fetch_company.py   ← Company data and reviews
│   │   └── evaluate.py    ← Single-model scoring (gemma4:e4b)
│   │
│   ├── intelligence/
│   │   ├── role_discovery.py  ← Infers reachable roles from dataset
│   │   ├── market_signals.py  ← Weekly market trend analysis
│   │   └── strategic_advisor.py ← Auto-triggers strategic advice
│   │
│   ├── telegram/
│   │   └── send.py        ← Daily / weekly / alert messages + feedback
│   │
│   └── utils/
│       ├── ollama_client.py ← Ollama wrapper with retries + JSON validation
│       └── cleaner.py     ← Text normalization
│
├── data/
│   └── jobs.db            ← SQLite database (gitignored)
├── logs/
│   └── pipeline.log
├── scripts/
│   ├── reporte_v3.py      ← Classifier HTML report generators (v3–v6)
│   ├── reporte_v4.py
│   ├── reporte_v5.py
│   ├── reporte_v6.py
│   ├── comparativa_classifier.py
│   ├── setup_cron.sh      ← Installs cron job for pipeline
│   ├── start_bot.sh       ← Starts Telegram bot
│   └── stop_bot.sh        ← Stops Telegram bot
└── tests/
    ├── unit/              ← Pure function tests (107)
    ├── integration/       ← DB + pipeline logic (64)
    └── fixtures/
        └── ollama/        ← JSON cassettes for Ollama calls (13)
```

---

## Setup

### Prerequisites

- Python 3.14+
- [Ollama](https://ollama.com/) running locally
- Apify account with API token (~$0.09 per pipeline run)
- Telegram bot token (via [@BotFather](https://t.me/botfather))

```bash
# Pull required model
ollama pull gemma4:e4b
```

### Install

```bash
git clone https://github.com/Veidos/job-intelligence-agent.git
cd job-intelligence-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Fill in: APIFY_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### Initialize database

```bash
python src/db/init_db.py
```

### Onboarding (first run only)

```bash
PYTHONPATH=. python src/onboarding/run.py --cv assets/cv.pdf
# Generates PERFIL.md — review and confirm before continuing
```

### Run the pipeline

```bash
# Full pipeline
PYTHONPATH=. python src/pipeline/run.py

# Individual steps
PYTHONPATH=. python src/pipeline/fetch.py
PYTHONPATH=. python src/pipeline/role_classifier.py
PYTHONPATH=. python src/pipeline/evaluate.py
PYTHONPATH=. python src/telegram/send.py --mode daily

# Dry run (no Apify, no Telegram)
PYTHONPATH=. python src/pipeline/run.py --dry-run
```

---

## Cost

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Apify actor start | ~$0.09 | Once per day |
| Ollama inference | $0.00 | Local, unlimited |
| Telegram | $0.00 | Free |

**~$2.70/month** at one run per day. Never run the Apify actor manually in development — always use `--dry-run`.

---

## Automation (Phase 5)

```cron
# Daily pipeline at 9:00 AM (configurable via Telegram)
0 9 * * * /path/to/.venv/bin/python /path/to/src/pipeline/run.py
```

Send time and number of daily offers are configurable via Telegram commands (Phase 5).

---

## Roadmap

> **Status legend:** ✅ complete (implemented + validated end-to-end) · 🟡 coded (implemented, validation pending via [TESTING.md](docs/TESTING.md)) · ⬜ not yet implemented

```
Phase 1 — Foundation        ✅ T-0 validated
Phase 2 — Onboarding        ✅ T-1 validated
Phase 3 — Base pipeline     🟡 Coded (validation pending)
  ├── fetch.py              🟡 Coded (T-2 ⏳ ADR-004)
  ├── role_classifier.py    ✅ Validated (v6 stable, ADR-005)
  ├── fetch_company.py      🟡 Coded (T-3 ⏳ ADR-004)
  ├── evaluate.py           🟡 Coded (T-5 ← tested)
  ├── send.py               🟡 Coded
  └── run.py (pipeline)     🟡 Coded
Phase 4 — Intelligence      ⬜ Pending
Phase 5 — Automation        🟡 Coded (validation pending)
  ├── cron + schedule       🟡 Coded
  ├── Telegram feedback     🟡 Coded
  └── feedback_processor    🟡 Coded
Phase 6 — Data Analysis/EDA ⬜ Planned
```

---

## Agent Context

This project uses the **Ledger Method** for AI-assisted development:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Full context for OpenCode / AI agents — read this first |
| `PLANS.md` | Live project state with task checklist |
| `MEMORIES.md` | Accumulated non-obvious learnings (prompts, field behavior, model quirks) |
| `PERFIL.md` | Candidate profile — source of truth for all evaluations |
| `docs/adr/` | Architecture Decision Records — 5 files: onboarding, CV check, classifier design, testing, etc. |
| `docs/TESTING.md` | Pipeline integration checklist — human/auto distinction |

> `PERFIL.md` is in `.gitignore`. Never auto-regenerate without explicit user confirmation.

---

## Privacy First

All LLM inference runs **locally via Ollama**. No CV content, personal context, or job evaluation data is sent to any external service except:

- **Apify** — job scraping only, no personal data involved
- **Telegram** — notification delivery only

The `personal_concerns` field (sensitive personal context) is never logged, printed to console, or included in error messages.

---

## Security Notes

- All credentials via environment variables, never hardcoded
- `PERFIL.md` and `data/jobs.db` are excluded from version control
- `personal_concerns` field is never logged or printed to console
