# Pipeline

## Prerequisites

Before the pipeline can fetch offers, `search_config` must contain a valid
`role_hierarchy`. This is populated by the keyword generator:

```bash
python -m src.onboarding.keyword_generator
```

See `src/onboarding/keyword_generator.py` for details. Run once after onboarding,
or whenever `PERFIL.md` changes significantly.

## Main Flow

```
run.py: fetch → classify → evaluate → send
```

Additionally, a static dashboard can be generated for inspection:
```bash
python src/pipeline/generate_dashboard.py   # reports/evaluations-v2.html
```

## 1. Fetch (fetch.py)

Fetches job offers from InfoJobs via Apify. Operates in **three sequential phases**.

### Phase 1 — `persist_raw_responses` (append-only)

1. Reads `APIFY_TOKEN` from environment (inside `run_fetch()`, not module-level)
2. Reads `search_config` from the database
3. Builds search URLs with geo/role hierarchy from `search_config.role_hierarchy`
4. Runs Apify actor (`lRxJmbuhggr0LU3uj`)
5. Persists **each item** in `apify_raw_responses` table (append-only, immutable)
   - `run_id`, `item_index`, `source_id`, `payload` (full item JSON), `processed=0`
   - `INSERT OR IGNORE` — idempotent per (run_id, item_index)
6. **Does not call any LLM** in this phase

### Phase 2 — `upsert_from_raw` (upsert in offers)

1. Reads `apify_raw_responses` where `run_id = current_run AND processed = 0`
2. For each raw row: deserializes `payload`, calls `_upsert_offer()` (previously `upsert_raw`)
3. On success: marks `processed = 1`
4. On failure: saves error message in `error` column, does not block the batch

`_upsert_offer()` extracts structural fields directly from Apify
(`title`, `city`, `companyName`, `link`, `contractType`, `teleworking`,
`description`, `salary`, etc.) + saves `raw_data` (full item JSON).
**No LLM call.**

### Phase 3 — `enrich_pending` (with LLM)

1. Selects offers with `raw_data IS NOT NULL AND enriched_at IS NULL`
2. For each offer: deserializes `raw_data`, calls `extract_fields_with_llm`
   (gemma4:e4b, temperature 0.0) to extract:
   - `description_clean` — plain text without HTML
   - `role_level` — junior / mid / senior
   - `skills_required` — core and secondary (name only, no level)
   - `experience_min`, `education_level`
   - `salary_min`, `salary_max`
3. Updates the offer and sets `enriched_at = NOW()`

**If the LLM fails:** the offer remains with `enriched_at IS NULL` and is
automatically retried on the next run. The raw offer is never lost.

**Output:** full `raw_data`, `description_raw`, and structural fields
available from Phase 1 — even if the LLM never succeeds.

### Key changes from the previous 2-phase design

| Before | After |
|--------|-------|
| `upsert_raw()` (single function) | `persist_raw_responses()` → `upsert_from_raw()` → `enrich_pending()` |
| Raw items persisted directly in `offers` | Raw items persisted first in `apify_raw_responses` (immutable), then upserted in `offers` |
| `APIFY_TOKEN` at module level | `APIFY_TOKEN` read inside `run_fetch()` |

## 2. Classify (role_classifier.py)

Classifies each offer according to the role catalog.

**Process:**
1. Gemma4 analyzes title + description of each offer
2. Assigns `role_normalized` from the role catalog
3. Assigns `relevance_flag`:
   - `core`: requirements match >70% of candidate profile
   - `adjacent`: 40–70% match
   - `stretch`: 20–40% match
   - `temporal`: viable bridge job
4. Updates the catalog if new roles are detected

## 3. Evaluate (evaluate.py)

Evaluates each offer against the candidate profile. **Deterministic calculation
with a single context prompt.**

### Score components

| Component | Weight | Source | Method |
|-----------|--------|--------|--------|
| `M_core` (core skills) | 0.45 | Python | Level multiplier per skill |
| `M_sec` (secondary skills) | 0.15 | Python | Level multiplier per skill |
| `F_exp` (experience) | 0.25 | Python | years_match · gap_multiplier |
| `F_fit` (context) | 0.15 | gemma4:e4b | Qualitative evaluation |

### Key rules

- **`level_required` is not persisted per skill.** It is resolved at
  evaluation time from the offer's `role_level_label` via the
  `ROLE_LEVEL_TO_SKILL_LEVEL` mapping.
- **`gap_severity` is computed in Python** (deterministic), not asked of the LLM.
- **Overqualification is not penalized** — the level multiplier caps at 1.0.
- **Final validation** (third prompt): detects real blockers
  (internship agreements, mandatory disability certificate) and validates
  `relevance_flag`.

See full scoring in [`docs/RATING.md`](docs/RATING.md).

## 4. Send (send.py)

Sends the daily summary via Telegram.

**Selection logic:**
- Score minimum: 0.35
- Maximum: 3 offers
- Priority: highest score first
- Range 0.35–0.54: add note "Incluida por falta de opciones superiores"

**Feedback:**
- `/f1 [text]` → feedback on offer 1
- `/f2 [text]` → feedback on offer 2
- `/f3 [text]` → feedback on offer 3
- `/dia [text]` → daily emotional context

## Comandos de referencia

### fetch.py

```bash
# Fetch completo: llama a Apify + upsert + enriquecimiento
python src/pipeline/fetch.py

# Fetch sin límite de ofertas (histórico completo)
python src/pipeline/fetch.py --max-items 0

# Fetch con límite personalizado
python src/pipeline/fetch.py --max-items 50

# Solo enriquecer ofertas pendientes con LLM (sin llamar a Apify)
python src/pipeline/fetch.py --enrich-only
```

`--enrich-only` es útil para reprocesar ofertas cuyo enriquecimiento falló
en ejecuciones anteriores. Re-intenta todas las ofertas con
`enriched_at IS NULL` sin coste de API.

### run.py

```bash
# Pipeline completo: fetch → classify → evaluate → send
python src/pipeline/run.py

# Sin fetch (solo classify + evaluate + send)
python src/pipeline/run.py --skip-fetch

# Simulación (no envía a Telegram)
python src/pipeline/run.py --dry-run
```

### Otros

```bash
# Clasificar ofertas pendientes
python src/pipeline/role_classifier.py

# Evaluar ofertas clasificadas
python src/pipeline/evaluate.py                # Por defecto 10 ofertas
python src/pipeline/evaluate.py --limit 0      # Todas las pendientes

# Generar HTML de evaluaciones
python src/pipeline/generate_dashboard.py      # reports/evaluations-v2.html

# Enviar resumen diario a Telegram
python src/telegram/send.py --mode daily

# Enriquecer datos de empresas desde ofertas
python src/pipeline/fetch_company.py
```

## Intelligence Modules (Pending)

These modules analyze patterns to generate strategic recommendations:

| Module | Function |
|--------|----------|
| `role_discovery.py` | Infers reachable roles from the offer dataset |
| `market_signals.py` | Computes weekly market signals |
| `strategic_advisor.py` | Detects triggers and generates strategic advice |

**Strategic Advisor triggers:**
- `no_calls_3_weeks`: applications > 5, calls = 0, weeks >= 3
- `market_cold_2_weeks`: market_temperature = 'cold' >= 2 weeks
- `skill_gap_detected`: skill in >40% offers and not in CV
- `role_pivot_signal`: avg match_score < 0.45 >= 4 weeks
