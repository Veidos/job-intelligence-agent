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
run.py: fetch → classify → enrich companies → evaluate → send
dashboard: server.py → http://localhost:8080 (web UI with feedback + applications)
```

Additionally, a static dashboard can be generated for inspection:
```bash
python src/pipeline/generate_dashboard.py   # reports/evaluations-v2.html
```

## 1. Fetch (fetch.py)

> **ADR-016 (completed):** Apify scraper ha sido reemplazado por un scraper propio
> (`infojobs_scraper.py`) que extrae datos estructurados completos (estudios, idiomas,
> conocimientos, experiencia) directamente del HTML de InfoJobs.

Actualmente obtiene ofertas mediante **scraper propio** con `curl_cffi` + BeautifulSoup.
Opera en **dos fases secuenciales**.

### Phase 1 — `persist_scraper_raw` (append-only)

1. Lee `search_config` de la base de datos
2. Construye URLs de búsqueda con geo/role hierarchy desde `search_config.role_hierarchy`
3. Invoca `InfoJobsScraper.search()` para cada URL — parsea el HTML de resultados con `InfoJobsParser.parse_search_html()`
4. Para cada oferta: invoca `InfoJobsScraper.get_detail()` → `InfoJobsParser.parse_detail_html()`
   que extrae:
   - Header: ciudad, modalidad, salario, contrato, experiencia, educación
   - Requisitos `<dl>`: estudios, experiencia, idiomas, conocimientos, sector
   - Descripción real (selectores semánticos, guard `len > 100`)
   - `published_at` desde texto plano (5 formatos: "Hace Xd", "Hace Xh", "Hoy", "Ayer", "DD de mes")
5. Persiste **cada item** en `scraper_raw_responses` (append-only, inmutable)
   - `offer_id`, `url`, `payload` (HTML completo), `processed=0`
   - `INSERT OR IGNORE` — idempotente por `UNIQUE(offer_id)`
6. **No llama a ningún LLM** en esta fase

### Phase 2 — `upsert_from_scraper_raw` (upsert en offers)

1. Lee `scraper_raw_responses` donde `processed = 0`
2. Para cada raw row: deserializa `payload` del HTML parseado, llama a `_upsert_offer_from_scraper()`
3. Extrae campos estructurados directamente del HTML parseado:
   `title`, `city`, `company`, `link`, `contract_type`, `work_mode`, `description_text`,
   `salary_min`, `salary_max`, `experience_min`, `education_level`, `skills`, `languages`, `sector`, `published_at`
4. Skills del HTML (sección `<dl>` "Conocimientos") van directamente a `core` — son requisitos estructurados del formulario de la oferta, no de la descripción libre.
5. `enriched_at` se setea en el mismo upsert — no hay Fase 3 separada.
6. On success: marca `processed = 1`
7. On failure: guarda error en columna `error`, no bloquea el batch

### Parámetros de búsqueda

- `--max-items` — número máximo de ofertas a scrapear por keyword (0 = sin límite)
- `--since-date` — filtro temporal: `_24_HOURS`, `_7_DAYS`, `_15_DAYS`, `ANY` (default: `_24_HOURS`)

### Comportamiento de `published_at`

InfoJobs no expone fechas ISO en el HTML. `_extract_published_at()` parsea texto relativo:
| Texto visible | Interpretación |
|---------------|---------------|
| "Publicada Hace 4d" | Hoy − 4 días |
| "Publicada Hace 2h" | Hoy (mismo día) |
| "Hoy" | Hoy |
| "Ayer" | Hoy − 1 día |
| "29 de may" | 2026-05-29 (asume año actual) |

Si falla el parseo, `published_at` queda `NULL` (ofertas expiradas).

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

## 2.5. Enrich Companies (fetch_company.py)

Enriches company information using qwen2.5:7b (temperatura 0.0):

1. Extracts company name from each offer (already in DB)
2. Calls qwen2.5:7b to enrich: sector, company size, description, linkedin_url
3. Upserts into `companies` table with `contact_person`, `contact_email`, `contact_phone`
4. Links companies to offers via `offers.company_id`

**If qwen2.5:7b fails:** company remains without enrichment; no retry logic.

## 3. Evaluate (evaluate.py)

Evaluates each offer against the candidate profile. **Deterministic calculation
with a single context prompt.**

### Score components

| Component | Weight | Source | Method |
|-----------|--------|--------|--------|
| `M_core` (core skills) | 0.45 | Python | Level multiplier per skill |
| `M_sec` (secondary skills) | 0.15 | Python | Level multiplier per skill |
| `F_exp` (experience) | 0.25 | Python | years_match |
| `F_fit` (context) | 0.15 | gemma4:e4b | Qualitative evaluation |

### Key rules

- **Skills evalúan presencia, no profundidad.** L es binario (1.0 si el candidato tiene la skill, 0.0 si no). La profundidad la captura `F_exp` mediante `experience_min_years` del scraper.
- **`gap_severity` is computed in Python** (deterministic), not asked of the LLM.
- **Final validation** (third prompt): detects real blockers
  (internship agreements, mandatory disability certificate) and validates
  `relevance_flag`.

See full scoring in [`docs/RATING.md`](docs/RATING.md).

## 4. Dashboard (server.py)

The primary interface is a local web dashboard. Serves at `http://localhost:8080`.

```bash
python src/dashboard/server.py
```

### Sections (redesign v2, ADR-015)

4 hierarchical sections, no admin/user mixing:

| # | Section | Purpose | Key Features |
|---|---------|---------|-------------|
| 1 | **🔍 Ofertas** (default) | Explore opportunities | 10-column table (Score, Título, Empresa, Ubicación, Modalidad, Publicado, Salario, Recomendación, Señal, Bloqueo). Sparkline semanal en header. Modal with collapsible description + scoring breakdown + skills + sticky CTA footer. |
| 2 | **💼 Aplicaciones** | Track applications | List with inline `<select>` status. Expandable notes/contact/date panel. "Ver oferta" button. |
| 3 | **🏢 Empresas** | Company intelligence | Table + 2 charts (top 5 by offers, sector distribution). |
| 4 | **📊 Monitor** | System health | Narrative sections: Resumen (KPIs) → Calidad de ofertas (score dist, salary dist, rec dist) → Distribución geográfica y modalidad (city stacked, work mode bar) → Mercado de skills (core, secondary, gap) → Precisión del modelo (recommendation×relevance, signal×rec, model accuracy) → Actividad (weekly activity, score trend, pipeline runs) → Embudo de aplicaciones. |

### Design decisions (v2)

| Decision | Rationale |
|----------|-----------|
| Ofertas as default landing | Candidate explores offers first, not pipeline stats |
| 10 columns (incl. Ubicación), no M_core/M_sec/F_exp/F_fit | Internal scoring hidden; collapsible breakdown in modal |
| filterBlocked default = off | Show blocked only on demand; green default feels oppressive |
| Sticky modal footer "Añadir a aplicaciones" | CTA always visible without scrolling |
| Description collapsible in modal | Full offer context without leaving dashboard |
| Applications as list with inline status | <20 apps makes kanban sparse; denser than timeline |
| Monitor narrative flow | Tells a story: Resumen → Calidad → Precisión → Actividad |
| Empresa charts client-side | Chart.js from `/api/companies`; no backend changes |
| filterHideExpired default = on | Ocultar ofertas >30 días (checkbox en Ofertas) |
| Age badge (🟢🟡🟠🔴⚫) | Días desde published_at, sin cambios en DB |
| Follow-up badges (Esperando/Follow-up/Insistir/Descartar) | 7/14/21 días desde applied_at, badge + overdue (🔔) |
| Follow-up table in Monitor | KPIs + tabla ordenada por urgencia (seguimiento próximo)

### API REST

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML |
| `/api/stats` | GET | Pipeline KPIs |
| `/api/offers?min_score=&rec=&signal=&rel=&search=&company_id=&limit=` | GET | Offers with filters |
| `/api/offers/<id>` | GET | Full detail + feedback + application |
| `/api/companies` | GET | Companies with offer count and avg score |
| `/api/feedback` | GET | All feedback (last 200) |
| `/api/feedback` | POST | Create feedback `{offer_id, raw_text}` |
| `/api/applications` | GET | All applications (last 500) |
| `/api/applications` | POST | Upsert application `{offer_id, status, notes, contact_name, next_action_date}` |
| `/api/applications/<id>` | DELETE | Remove application |
| `/api/runs` | GET | Pipeline run history |

### Tech

- **Framework:** Flask (local, no ORM)
- **Charts:** Chart.js v4 via CDN
- **Styles:** Custom CSS theme (dark)
- **No external dependencies** beyond Flask and Chart.js CDN

## 5. Send (send.py) — optional

Sends the daily summary via Telegram. Optional — the dashboard is the primary interface.

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
# Fetch completo: scraper propio + upsert + enriquecimiento LLM
python src/pipeline/fetch.py

# Fetch sin límite de ofertas (histórico completo)
python src/pipeline/fetch.py --max-items 0

# Fetch con límite personalizado
python src/pipeline/fetch.py --max-items 50

# Fetch con filtro temporal (default: _24_HOURS)
python src/pipeline/fetch.py --since-date _7_DAYS    # Últimos 7 días
python src/pipeline/fetch.py --since-date ANY        # Sin filtro de fecha

# Pipeline completo con filtro temporal
python src/pipeline/run.py --since-date _24_HOURS    # Solo últimas 24h (default)

### run.py

```bash
# Pipeline completo: fetch → classify → evaluate → send
python src/pipeline/run.py

# Sin fetch (solo classify + evaluate + send)
python src/pipeline/run.py --skip-fetch

# Simulación (no envía a Telegram)
python src/pipeline/run.py --dry-run
```

### dashboard

```bash
# Arrancar servidor web (http://localhost:8080)
python src/dashboard/server.py

# Puerto personalizado
python src/dashboard/server.py --port 9090
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
