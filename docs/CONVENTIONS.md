# Code Conventions

## Python

- **Version:** 3.14+
- **Type hints:** Required on all public functions
- **Imports:** Absolute from `src/`. No relative imports

## Style and Naming

| Type | Convention |
|------|------------|
| Variables, columns | snake_case |
| Classes | PascalCase |
| Constants | UPPER_CASE |
| Booleans | is_*, has_*, enable_* |

## Linter and Formatting

```bash
ruff check src/
ruff format src/
```

Always run before marking a task as complete.

## Logging

- Use Python's standard `logging`
- Do not use `print()` except in interactive onboarding scripts
- Include context in errors (not just the message)

## Error Handling

### Ollama
- Retry up to 3 times with exponential backoff
- If it fails: log and continue with the next offer
- Use custom exceptions: `OllamaError`, `OllamaJSONError`

### InfoJobs API
- Log error with full context in `search_runs`
- Do not abort the pipeline for partial errors
- Continue with the offers that could be processed

### JSON from Models
- Always validate the schema before inserting into DB
- If JSON is invalid, retry the prompt once with additional format instructions
- Use helpers `json_serialize` / `json_deserialize`

## Environment Variables

- All in `.env` (DO NOT commit)
- Load with `python-dotenv`
- Never hardcode credentials

## Ledger Method

This project uses the Ledger Method for tracking:

- **PLANS.md:** Keep updated with status of each phase, completed tasks, pending items, and blockers
- **MEMORIES.md:** Record non-obvious learnings (effective prompts, reliable fields, model performance)

Update both after completing each module or significant task.

## Implementation Phases

```
PHASE 1 — Foundation
  init_db.py + complete schema.sql
  ollama_client.py with retries and JSON validation
  Connection test for Telegram, Ollama, InfoJobs API

PHASE 2 — Onboarding
  cv_extractor.py (gemma4 → structured data)
  interviewer.py (gemma4 → sequential questions)
  Generation of PERFIL.md
  Save to candidate_profile (DB)

PHASE 3 — Base Pipeline
  fetch.py, evaluate.py, send.py, run.py
  role_classifier.py

PHASE 4 — Intelligence
  role_discovery.py, market_signals.py, strategic_advisor.py

PHASE 5 — Automation
  Cron configuration, logging and monitoring, end-to-end tests
```

Do not advance to the next phase without the previous one being tested and working.

## Language

All documentation, ADRs, and code comments are written in English.
ADR-001 through ADR-008 have been translated for consistency.
All new ADRs (ADR-009 onwards) must be written in English from the start.
