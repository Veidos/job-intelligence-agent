# Job Intelligence Agent

> Personal career intelligence system. Extracts job offers from InfoJobs, evaluates CV match using local LLMs (Ollama), and delivers daily recommendations via Telegram.

Built for the Spanish job market. Fully offline-first — no data leaves your machine except the Telegram notification.

---

## How It Works
InfoJobs (Apify)
│
▼
fetch.py ──────────────────────────────── SQLite (offers)
│ │
▼ ▼
fetch_company.py ── SQLite (companies) evaluate.py
│
┌──────────┴──────────┐
│ │
qwen2.5-coder gemma4:e4b
(technical match) (HR + context)
│ │
└──────────┬───────────┘
│
match_score
│
send.py ──► Telegram

text

Two models, one pipeline:

| Model | Role | Temperature | Output |
|---|---|---|---|
| `qwen2.5-coder:7b` | Technical evaluator | `0.1` | Structured JSON scores |
| `gemma4:e4b` | HR reasoning + strategy | `0.4` | Contextual analysis + advice |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.14+ |
| Database | SQLite (WAL mode) |
| ORM | SQLAlchemy 2.0 |
| Local LLMs | Ollama (`qwen2.5-coder:7b`, `gemma4:e4b`) |
| Job data source | Apify — InfoJobs Spain Jobs Scraper |
| Notifications | Telegram Bot API |
| Linting | Ruff |
| Scheduling | cron |

---

## Project Structure
job-intelligence-agent/
├── AGENTS.md ← AI agent context (read by OpenCode)
├── PERFIL.md ← Candidate source of truth (DO NOT auto-regenerate)
├── PLANS.md ← Project ledger (phases + task status)
├── MEMORIES.md ← Accumulated system learnings
├── requirements.txt
├── .env ← Credentials (never commit)
│
├── assets/
│ └── cv.pdf
│
├── src/
│ ├── db/
│ │ ├── init_db.py ← Schema initializer
│ │ ├── schema.sql ← Single source of truth for DB structure
│ │ └── models.py ← SQLAlchemy models
│ │
│ ├── onboarding/
│ │ ├── run.py ← Orchestrates full onboarding
│ │ ├── cv_extractor.py ← qwen2.5 extracts structured data from CV
│ │ └── interviewer.py ← gemma4 conducts guided interview
│ │
│ ├── pipeline/
│ │ ├── run.py ← Full pipeline (fetch → eval → send)
│ │ ├── fetch.py ← InfoJobs via Apify → clean → upsert DB
│ │ ├── fetch_company.py← Company data and reviews
│ │ └── evaluate.py ← Dual-model scoring
│ │
│ ├── intelligence/
│ │ ├── role_discovery.py ← Infers reachable roles from job dataset
│ │ ├── market_signals.py ← Weekly market trend analysis
│ │ └── strategic_advisor.py ← Auto-triggers strategic advice
│ │
│ ├── telegram/
│ │ └── send.py ← Daily / weekly / alert messages
│ │
│ └── utils/
│ ├── ollama_client.py ← Ollama wrapper with retries + JSON validation
│ └── cleaner.py ← Text normalization
│
├── data/
│ └── jobs.db ← SQLite database (never commit)
├── logs/
│ └── pipeline.log
└── tests/
└── test_phase1.py

text

---

## Setup

### 1. Prerequisites

- Python 3.14+
- [Ollama](https://ollama.com/) running locally
- Apify account with API token
- Telegram bot token

```bash
# Pull required models
ollama pull qwen2.5-coder:7b
ollama pull gemma4:e4b
```

### 2. Install

```bash
git clone https://github.com/Veidos/job-intelligence-agent.git
cd job-intelligence-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Fill in: APIFY_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### 4. Initialize database

```bash
python src/db/init_db.py
```

### 5. Onboarding (first run only)

```bash
python src/onboarding/run.py --cv assets/cv.pdf
# Generates PERFIL.md — review and confirm before continuing
```

### 6. Run the pipeline

```bash
# Full pipeline
python src/pipeline/run.py

# Individual steps
python src/pipeline/fetch.py
python src/pipeline/evaluate.py
python src/telegram/send.py --mode daily
```

---

## Scoring System

Match score composed of two independent blocks:

### Block A — Technical (qwen2.5, 60 pts)

| Criterion | Weight |
|---|---|
| Hard skills overlap | 0–25 |
| Experience match | 0–15 |
| Education level | 0–10 |
| Location / work mode | 0–10 |

### Block B — HR Context (gemma4, 40 pts base)

| Criterion | Weight |
|---|---|
| Career trajectory coherence | 0–15 |
| Recency of relevant experience | 0–15 |
| Market competitiveness | 0–10 |
| Penalty (from personal context) | 0–(−30) |

### Rating labels

| Score | Label |
|---|---|
| 75–100 | 🟢 Prioritario |
| 55–74 | 🟡 Aplicar |
| 35–54 | 🟠 Con expectativas bajas |
| 0–34 | 🔴 No aplicar |

Daily Telegram sends the **top 3 offers with score ≥ 35**. If none qualify: `"Sin ofertas relevantes hoy."`.

---

## Intelligence Layer (Phase 4)

The system accumulates data over time to surface strategic signals:

- **Role Discovery** — finds reachable roles with skill overlap, even outside initial search queries
- **Market Signals** — weekly trends: volume, competition, salary, remote %, emerging skills
- **Strategic Advisor** — auto-triggers advice when patterns are detected (cold market, recurring skill gap, low avg score)

---

## Data Analysis (Planned — Phase 6)

As the SQLite dataset grows, a dedicated analysis layer will provide:

- **EDA notebooks** — exploratory analysis of accumulated offers (salary distributions, skill frequency, remote %, location heatmaps)
- **Match score evolution** — personal trend over time (are scores improving as skills develop?)
- **Market benchmarking** — compare personal profile gap vs. market demand over weeks
- **Visualizations** — Plotly/Matplotlib dashboards generated from the live `jobs.db`

> The database schema is designed with this phase in mind — all fields are stored raw alongside normalized versions to support flexible future analysis.

---

## Automation (Phase 5)

```cron
# Daily pipeline at 9:00 AM
0 9 * * * /path/to/.venv/bin/python /path/to/src/pipeline/run.py
```

---

## Roadmap
Phase 1 — Foundation ✅ Complete
Phase 2 — Onboarding ✅ Complete
Phase 3 — Base pipeline 🔄 In progress
├── fetch.py ✅ Done
├── fetch_company.py ⬜ Pending
├── evaluate.py ⬜ Pending
├── send.py ⬜ Pending
└── run.py (pipeline) ⬜ Pending
Phase 4 — Intelligence ⬜ Pending
Phase 5 — Automation ⬜ Pending
Phase 6 — Data Analysis/EDA ⬜ Planned

text

---

## Agent Context

This project uses the **Método Ledger** for AI-assisted development:

| File | Purpose |
|---|---|
| `AGENTS.md` | Full context for OpenCode / AI agents — read this first |
| `PLANS.md` | Live project state with task checklist |
| `MEMORIES.md` | Accumulated non-obvious learnings (prompts, field behavior, model quirks) |
| `PERFIL.md` | Candidate profile — source of truth for all evaluations |

> `PERFIL.md` is in `.gitignore`. Never auto-regenerate it without explicit user confirmation.

---

## Security Notes

- All credentials via environment variables, never hardcoded
- `PERFIL.md` and `data/jobs.db` are excluded from version control
- `personal_concerns` field is never logged or printed to console
