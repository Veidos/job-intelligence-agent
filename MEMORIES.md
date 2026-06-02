# MEMORIES.md — Aprendizajes del Sistema

## Configuración del proyecto
- Python 3.14+ requerido
- pytest instalado para tests
- Ollama ejecutándose localmente en http://localhost:11434
- gemma4:e4b como único modelo (técnico + HR, qwen2.5 eliminado)

## Suite de tests
- Estructura: tests/unit/ (funciones puras), tests/integration/ (DB + lógica)
- Fixture principal: `test_db` — temp file con schema.sql, rollback por test
- Fixture `test_conn` — wrapper sqlite3 compatible con save_evaluation
- Fixtures de datos: `sample_perfil_text`, `sample_offer`, `sample_offer_senior`, `sample_offer_no_exp`, `sample_offer_temporal`, `sample_offer_with_impossible_requirements`
- 167 tests: 107 unit, 30 cassette-based integration, 10 pipeline — todos passing
- Ollama cassettes: 13 JSON fixtures en tests/fixtures/ollama/ (no vcrpy)
- test_classifier_cassettes.py: usa test_engine (Connection) no test_db (Cursor) — role_classifier usa conn.cursor()
- test_evaluate_cassettes.py: cassettes directos (no wrapped), mock_ollama_call con side_effect para secuencias
- test_fetch_cassettes.py: call_args.kwargs para extraer prompt (no call_args[0][1])
- test_pipeline.py: flujo completo con stateful mocks (call_count++) para secuencias de llamadas
- ruff fix eliminó 6 imports sin usar de test_pipeline.py
- PLANS.md actualizado con 167 tests passing

## Extracción de CV (cv_extractor.py)
- Usa gemma4:e4b para extracción estructurada de CV
- Límite de texto: 12000 caracteres (primeras páginas del PDF)
- Campos extraídos: full_name, location_current, skills_technical (con nivel), education, experience, languages, projects
- Skills tienen nivel: básico (bootcamp), intermedio (freelance), avanzado (trabajo formal)
- employment_gap_years se calcula matemáticamente (excluye proyectos académicos)
- Si el modelo falla en devolver JSON, ollama_client reintenta con instrucción adicional
- is_academic_or_training() detecta y excluye bootcamps, prácticas, proyectos académicos

## Prompts efectivos
- gemma4:e4b: instrucción explícita "responde UNICAMENTE con JSON valido" + esquema de campos
- Temperatura 0.1 para extracción determinista
- Pensamiento paso a paso para razonamiento complejo

## Fetch y extracción de campos
- `fetch.py` usa Apify (actor lRxJmbuhggr0LU3uj) para scrapear InfoJobs.
- Estructura del actor: `item["offer"]["code"]`, `item["offer"]["teleworking"]`, etc.
- `extract_fields_with_llm` usa gemma4:e4b para enriquecer campos (description_clean, skills_required, etc.)
- `upsert_offer` debe usar nombres exactos del schema.sql: `description_raw` (no `description`), `experience_min` (no `experience_years`), `fetched_at` (no `scraped_at`).
- Salarios: el schema tiene `salary_min` (REAL) y `salary_max` (REAL). Parsear desde texto con regex o desde gemma4.
- `search_url` NO existe en la tabla `offers`; no incluir en INSERT.
- `source_id` puede ser None si el actor falla; validar siempre antes de upsert.
- gemma4:e4b enriquece campos pasando el item completo (no solo `offer_data`) para contexto.
- `cleaner.py` limpia descripciones eliminando exceso de saltos de línea y espacios.

## URLs de InfoJobs
- `sinceDate=LAST_DAY` no funciona en URLs de InfoJobs (parámetro no soportado).
- Deduplicación se hace exclusivamente por `source_id` en DB (ya implementado).
- Usar `sortBy=PUBLICATION_DATE` para priorizar ofertas recientes en los resultados.

## Arquitectura de búsqueda y escalabilidad
- El sistema usa **source_adapter pattern** para escalabilidad multi-país.
  Ahora solo InfoJobs (España). Diseñado para añadir Indeed, LinkedIn etc
  sin reescribir fetch.py.
- La expansión geográfica y de rol es genérica: se infiere desde PERFIL.md
  vía gemma4:e4b, nunca hardcodeada.

## Configuración del usuario (user_settings)
- `user_settings` controla hora de envío, número de ofertas y modo
  (morning/night). En Fase 5 se gestiona vía comandos de Telegram.
  `fetch.py` y `send.py` leen siempre desde esta tabla, nunca hardcodean.
- Apify MCP se implementa en Fase 5. `fetch.py` usa REST API ahora.
  El adaptador será intercambiable sin cambiar la lógica del pipeline.

## Sistema de feedback (Telegram)
- Comandos: /f1 /f2 /f3 para feedback sobre ofertas 1-3 del día, /dia para contexto emocional.
- El feedback NO filtra ofertas futuras. Es contexto psicológico que gemma4 usa para añadir notas personalizadas en evaluaciones.
- Loop semanal comprime y resume feedback para no crecer infinitamente (feedback_processor.py — Fase 5).
- `daily_position` en `offer_evaluations` referencia la posición del mensaje diario para ligar feedback con oferta correcta.
- Tablas: `user_feedback` almacena mensajes crudos, `user_psychology` almacena el summary evolutivo comprimido.

## CV freshness check (SHA-256 en run.py)

- `run.py` calcula SHA-256 de `assets/cv.pdf` al inicio y lo compara con `.cv_hash`
- Si el hash cambia y hay TTY: pregunta interactiva "¿Regenerar PERFIL.md?"
- Si responde sí: ejecuta onboarding completo (extracción + entrevista) y continúa pipeline
- Si responde no o es headless (cron): pipeline detenido, warning pide onboarding manual
- `--dry-run` salta el check completamente (no hay efectos laterales)
- `.cv_hash` se guarda en raíz del proyecto (gitignored)
- Testeado: ambos flujos (TTY y headless) verificados el 2026-05-22

## Modelos Ollama — Decisión de diseño

- gemma4:e4b como único modelo para TODO el pipeline (técnico + HR)
- qwen2.5-coder:7b eliminado tras testeo: no razonaba bien en contexto amplio
- gemma4:e4b usa think=True para razonamiento complejo (evaluación, clasificación)
- Para extracción de campos planos en fetch.py: gemma4:e4b funciona bien (no requiere qwen2.5)

## Bugs detectados por tests

### save_evaluation — columnas faltantes (INSERT vs schema)
- `save_evaluation` en evaluate.py usaba 23 placeholders en INSERT
  pero la tabla `offer_evaluations` tiene 28 columnas (incluye cv_version_id,
  company_fit_score, company_green_flags, company_red_flags, interview_prep)
- El fix añade las 7 columnas faltantes al INSERT
- Error resultante: `sqlite3.OperationalError: 24 values for 23 columns`

### pre_filtro_requisitos_imposibles — comparison bug en PROFILE_CHECK_PATTERNS
- El patrón `PROFILE_CHECK_PATTERNS` usa tuples `(pattern, kw)` pero
  el código original comparaba `pattern == "carnet"` (string vs regex pattern object)
- Nunca matcheaba, el carné de conducir nunca se detectaba
- Fix: cambiar tupla a `(pattern, kw)` y comparar con `kw` (evaluate.py:78-87)

### Ollama cassettes — estructura de JSON directa
- Los cassettes deben ser JSON plano (no envuelto en `{"response": "..."}`)
- `ollama_call` internamente extrae JSON, los cassettes ya deben contener el dict parsed
- CASSETTES[name] es directamente el dict con keys del JSON de respuesta

## Fetch en dos fases (refactor mayo 2026)

- `upsert_raw()` reemplazó a `upsert_offer()` para separar persistencia
  de Apify del enriquecimiento con LLM
- `raw_data` almacena el JSON completo del item Apify para re-enriquecimiento
- `enriched_at IS NULL` sirve como flag de reintento automático
- `role_level_label` almacena el seniority (junior/mid/senior) inferido por el LLM
- `level_required` por skill ya no se persiste desde fetch — se resuelve en
  evaluate.py desde `ROLE_LEVEL_TO_SKILL_LEVEL` según `role_level_label`
- `parse_skills_required` acepta tanto objetos dict como strings planos
  (backward-compat con datos legacy en DB)
- `_ensure_skill_obj()` normaliza cualquier formato de skill a
  `{"name": str, "level_required": str|None}`
- Las columnas nuevas (`raw_data`, `enriched_at`, `role_level_label`) se
  añaden vía `src/db/migrate.py`, no con ALTER TABLE ad-hoc

## Fetch en tres fases + apify_raw_responses (mayo 2026)

- `fetch.py` ahora opera en 3 fases secuenciales:
  1. `persist_raw_responses()` — guarda cada item Apify en `apify_raw_responses` (append-only, inmutable)
  2. `upsert_from_raw()` — lee raw responses pendientes, llama a `_upsert_offer()` (antes `upsert_raw`)
  3. `enrich_pending()` — sin cambios
- `apify_raw_responses` es tabla append-only: nunca se actualiza un payload, solo se marca `processed=1`
- `_upsert_offer()` es privada (underscore), solo llamada desde `upsert_from_raw()`
- `APIFY_TOKEN` se lee dentro de `run_fetch()` vía `os.getenv()`, no en module-level

## Keyword generator (keyword_generator.py)

- Flujo: `PERFIL.md` → `generate_keywords()` [gemma4:e4b] → `save_to_search_config()` → `search_config.role_hierarchy`
- `ollama_call()` no acepta parámetro `system` — el system prompt se incrusta en el user prompt
- `--manage` permite conservar keywords por número y añadir nuevas manualmente, sin tocar el LLM
- `think=True` se envía en el payload pero gemma4:e4b no siempre devuelve el campo `think` en la respuesta
- El prompt para generar keywords debe usar reglas de comportamiento (no hardcode de títulos):
  - Sin indicadores de seniority
  - Versiones en inglés y español de los mismos roles
  - Solo títulos que existan realmente en InfoJobs España
  - Exactamente `MAX_KEYWORDS` títulos únicos (sin duplicados garantizado por dedup en Python)

## Enriquecimiento con think=True y num_ctx (mayo 2026)

- `extract_fields_with_llm` sin `think=True` fallaba en ~30% de ofertas (respuesta no-JSON)
- Fix: `think=True` + `num_ctx=8192` → **92/92 ofertas enriquecidas, 0 errores**
- `ollama_call()` ahora acepta `num_ctx` como parámetro (default 4096, backward-compat)
- `_call_ollama_raw()` pasa `num_ctx` en el payload `options`
- El progreso de `enrich_pending()` ahora loguea en INFO: `[N/total] source_id — enriquecida`

## parse_salary — formato dict de Apify (mayo 2026)

- Apify actor `easyapi/infojobs-job-scraper` devuelve `salary` como dict estructurado:
  `{"range": {"min": 30000, "max": 33000}, "period": "YEAR", "currency": "EUR"}`
- `parse_salary()` acepta ahora ambos formatos: dict estructurado y string legacy
- Si es dict, extrae `range.min` y `range.max` directamente
- Si es string, aplica regex legacy

## fetch.py — argumentos CLI (mayo 2026)

- `--max-items 0`: omite `maxItems` del payload Apify → sin límite de resultados
  Anteriormente siempre enviaba `maxItems: 30` en el payload.
- `--enrich-only`: solo reprocesa `enrich_pending()` sin llamar a Apify.
  Útil para reintentar ofertas con `enriched_at IS NULL` tras corregir parámetros.

## employer_id desde companyLink (mayo 2026)

- API InfoJobs vía Apify ya no devuelve `offer.author.id` para `employer_id`
- `companyLink` tiene dos formatos:
  1. `https://www.infojobs.net/{company}/em-i{HASH}` → extraer hash después de `em-i`
  2. `https://{subdomain}.ofertas-trabajo.infojobs.net` → extraer subdominio (1:1 con empresa)
- `_extract_employer_id()` implementa ambas estrategias, saltando subdominio `www`
- 92/92 ofertas tienen `employer_id` poblado tras backfill desde `raw_data`
- `fetch_company.py` usa `employer_id` como `infojobs_company_id` — compatible con ambos formatos

## Company enrichment con qwen2.5:7b (mayo 2026)

- `fetch_company.py` rediseñado: en lugar de crear filas vacías, agrupa ofertas por
  `employer_id` y envía a qwen2.5:7b para inferir sector, tamaño, descripción y flags.
- MODEL_COMPANY = "qwen2.5:7b" añadido en ollama_client.py con temperatura 0.0.
- Separación de responsabilidades: gemma4:e4b para evaluación compleja, qwen2.5:7b
  para extracción estructurada ligera.
- InfoJobs company pages tienen bot protection (Distil Networks) — no fiables para
  scraping automatizado. La inferencia desde ofertas agregadas es más robusta.
- Prompt para qwen2.5:7b debe forzar `size_range` como valor único del enum
  (el modelo tiende a mezclar variantes como "grande | gran_empresa" si no se
  especifica correctamente).
- Stale rule: solo enriquecer si `sector IS NULL` (Opción A). Simple y efectivo.
- Columnas nuevas en companies: llm_description, green_flags, red_flags,
  llm_confidence, enriched_by_llm_at, llm_model (sigue el patrón model_technical
  de offer_evaluations).
- 68 empresas enriquecidas en ~7 minutos, 0 errores. C/U toma ~3-4s en qwen2.5:7b.

## Modelos hardcodeados eliminados (mayo 2026)

- fetch.py, keyword_generator.py, role_classifier.py usaban `model="gemma4:e4b"` hardcodeado
- Todos ahora importan y usan `MODEL_TECHNICAL` desde ollama_client.py
- role_classifier.py añadió `think=True` + parámetro `model: str = MODEL_TECHNICAL` en classify_offer()
- Patrón establecido: MODEL_TECHNICAL (gemma4), MODEL_HR (gemma4), MODEL_COMPANY (qwen2.5:7b)
## Triada de documentación (ADR-009)

- `MEMORIES.md`: aprendizajes permanentes (ciclo de vida: infinito)
- `PLANS.md`: checklist de fases y tests (ciclo de vida: por fase)
- `HANDOFF.md`: estado de sesión, próximo paso, blockers (ciclo de vida: por sesión — se sobreescribe)
- `AGENTS.md` instruye: "Actualizar HANDOFF.md al final de la sesión" + "Leer HANDOFF.md al inicio"
- La documentación se actualiza en la misma sesión que el código, no después

## candidate_years como span desde fechas (ADR-012)

- `load_experience_years_from_perfil()` usaba una regex que buscaba "X años de experiencia" textual
- PERFIL.md no tiene esa frase explícita → siempre devolvía 0.0
- Fix: añadir fallback que parsea `**Duración:**` en `## Experiencia` y calcula el span
  (mes más reciente − mes más temprano) / 12
- El span evita inflar por solapamientos entre empleos
- Para el perfil actual: May 2018 → Sep 2022 = 4.3 años
- La sección regex debe evitar coincidir con `###` dentro de `## Experiencia`
  usando `(?=\n##[^#]|\Z)` en vez de `(?=\n##|\Z)`

## Educación como skills de dominio (ADR-012)

- `load_skills_from_perfil()` ahora también parsea `## Educación` de PERFIL.md
- Cada título académico se añade al skills_map con nivel "avanzado"
- Esto permite que el LLM de Step 1 detecte semánticamente competencias de dominio
  (ej: "Ingeniería Técnica Industrial" → "Ingeniería Industrial")
- El substring match en compute_skill_score también se beneficia: "ingeniería industrial"
  está dentro de "ingeniería técnica industrial, especialidad mecánica"
- Bootcamps también se capturan pero no interfieren porque ningún skill de oferta
  los referencia

## Partial save + upsert en evaluate.py (ADR-012)

- save_evaluation() ahora hace upsert (SELECT → INSERT/UPDATE) para evitar duplicados
  si el proceso se re-ejecuta sobre una oferta parcial
- `partial=True`: guarda Steps 1–5 sin marcar is_evaluated=1
- `update_evaluation_final()`: UPDATE los campos de Step 6 + marca is_evaluated=1
- El loop en run_evaluate() ahora guarda parcial tras Step 5 y final tras Step 6
- Si Step 6 crashea, la evaluación parcial sobrevive en DB para ser retomada
- Útil combinado con el prompt de requisito_imposible en evaluate_final()

## Prompt de evaluate_final: titulación obligatoria como bloqueo

- El prompt original no incluía "titulación académica obligatoria" como ejemplo
  de requisito_imposible → el LLM trataba los Máster Oficiales como gap de dominio
- Fix: añadir "titulación académica obligatoria que el candidato no posee" a los
  ejemplos de apply_block
- Resultado: ofertas con requisito académico explícito (AEMET, ID 338) ahora
  detectan el bloqueo correctamente
- Ofertas donde el título es contexto de dominio (observador pesquero, ID 348) no
  se bloquean — el LLM distingue entre requisito legal y preferencia contextual
- Comportamiento aceptado: el score bajo ya filtra las que no se bloquean

## Batch 2 + full evaluate (mayo 2026)

- Batch 2 (IDs 326, 334, 325, 315, 369) validado: comportamiento consistente con Batch 1
  - Scores 30–48, el más alto Data Analyst @ BETWEEN (48, Con expectativas bajas)
  - ID 325 bloqueado por requisito_imposible (catalán alto) — prompt generaliza bien
  - ID 369 (process_engineer core): score 0.44, educación industrial mapeada correctamente
- Full evaluate: 82 ofertas, 0 errores, score promedio 0.29
- Solo 2 ofertas alcanzan "Aplicar" (≥55): ANALISTA DATOS @ RECACOR (63), Ingeniero Procesos @ Etalentum (62)
- Coherente con perfil bootcamp + gap 3.7a — la mayoría en "No aplicar" (<35)

## Bug case-sensitive en substring match (evaluate.py:259)

- `compute_skill_score()` comparaba `name_lower in cand_name or cand_name in name_lower`
- `cand_name` no se pasaba a lowercase → `"SQL" in "sql avanzado"` era False en Python
- Skills que el LLM no detectaba como presentes perdían el substring match de respaldo
- Fix: `.lower()` en ambos lados de la comparación
- Impacto práctico mínimo para este perfil, pero preventivo para batches futuros

## Dashboard de evaluaciones (legacy static HTML)

- Patrón legacy: `src/pipeline/generate_dashboard.py` → `reports/evaluations-v2.html`
- Chart.js vía CDN, datos embebidos como `const DATA = [...]` JSON (92 registros)
- **OBSOLETO desde T-5f:** Reemplazado por Flask web dashboard

## Flask Dashboard (T-5f, junio 2026)

### Arquitectura
- **Framework:** Flask (¿por qué no FastAPI? Porque es un dashboard local de 9 endpoints, no una API pública. Flask + Jinja2 es el nivel de complejidad correcto.)
- **No usa ORM:** SQLite directo vía `sqlite3` — las consultas son simples (SELECT, INSERT, DELETE) y no hay migrations complejas.
- **SPA con Jinja2:** El backend sirve HTML+JS en una sola página (`dashboard.html`), los datos se cargan vía fetch() desde 9 endpoints API REST.
- **Chart.js v4 vía CDN** para gráficos (igual que el dashboard legacy).
- **Static file serving:** Flask sirve `app.js` y `style.css` desde `src/dashboard/static/`.

### 6 Secciones
1. **📊 Pipeline** — KPIs (total, evaluadas, pendientes, empresas, feedbacks, aplicaciones, avg score) + doughnut distribución
2. **📋 Evaluaciones** — Tabla sortable/filterable (score, M_core, M_sec, F_exp, F_fit, recomendación, señal, empresa, título). Modal detalle: breakdown scores + skills table + HR verdict + inline feedback form + application tracker
3. **🏢 Empresas** — 68 empresas con sector, tamaño, flags, avg score. Click → filtra ofertas.
4. **💬 Aplicaciones** — Timeline semanal (CSS puro, no FullCalendar). Estados: applied → interviewing → rejected → offer → accepted.
5. **📈 Estadísticos** — 4 charts: score distribution (histogram), recommendation by relevance (stacked bar), signal by recommendation (clustered bar), score trend (line)
6. **⚙️ Runs** — Pipeline runs desde `search_runs`

### API REST
| Endpoint | Description |
|----------|-------------|
| GET `/api/stats` | Pipeline KPIs |
| GET `/api/offers?min_score=&rec=&signal=&rel=&search=&company_id=&limit=` | Filtered offers |
| GET `/api/offers/<id>` | Full detail + feedback + application |
| GET `/api/companies` | Companies with stats |
| GET/POST `/api/feedback` | List/create feedback |
| GET/POST `/api/applications` | List/upsert applications |
| DELETE `/api/applications/<id>` | Remove application |
| GET `/api/runs` | Pipeline history |

### Tabla applications
- Columnas: `offer_id`, `applied_at`, `status` (applied/interviewing/rejected/offer/accepted/archived), `notes`, `contact_name`, `next_action_date`
- Tabla separada de `user_feedback` porque representan conceptos diferentes: feedback es evaluación del usuario sobre la calidad del match; applications es estado de seguimiento de candidatura.
- `contact_name` y `next_action_date` añadidos desde el principio por el principio "cheap now, expensive later" — es fácil ignorarlos si no se usan, difícil añadirlos después cuando ya hay datos.
- Timeline renderiza como CSS grid semanal (no FullCalendar). MVP suficiente.

### Decisiones de diseño
- **Dashboard reemplaza Telegram como interfaz principal.** Telegram se mantiene como canal secundario (opcional). El pipeline termina en el dashboard.
- **location_match no se muestra en el dashboard.** No filtra en la práctica (es puramente informativo y correlaciona 1:1 con work_mode).
- **Flask elegido sobre FastAPI** por simplicidad — 9 endpoints locales no justifican Pydantic + ASGI.
- **Aplicaciones como tabla separada** de offer_evaluations porque es estado controlado por el usuario, no por el pipeline.
- **Sin FullCalendar** — timeline CSS semanal es más ligero y suficiente para MVP.
- **`_normalize_none()` en evaluate.py** corrige string "null"/"None" que gemma4 a veces emite en lugar de JSON null (IDs 301, 303, 318 tenían literal "null" en apply_block antes del fix).

### Temas de estilo
- Dark theme completo (css custom, sin framework)
- Modal de detalle con scroll, 3 columnas en desktop
- Tabla sticky header + row hover
- Badge verde "Sin bloqueo" para apply_block NULL
- Timeline: tarjetas con colores por estado, agrupadas por semana
- Responsive (se apila en móvil)

## Bug: sort crash por columnas sin flecha (junio 2026)

- Columnas sin `<span class="arrow"></span>` → `querySelector('.arrow')` devuelve `null`
- Click handler accedía `.classList` sobre null → `TypeError` → no llegaba a `render()`
- Fix dual: (A) 14/14 columnas ahora tienen `<span class="arrow">`, (B) safety con `if(arrow)` opcional
- Formato fecha: helper `dateFmt()` con `MONTHS` array en español (`Ene`, `Feb`, `Mar`...)
  publicado como "20 May" en vez de "05-20" ISO slice
- Renombrado `reports/dashboard.html` → `reports/evaluations-v1.html` (v1 legacy) y `reports/evaluations-v2.html` (actual)

## Scoring rebalance — ADR-013 (junio 2026)

### Problema diagnosticado

1. **F_exp plana en 55** para las 92 ofertas. Causa raíz: `get_pending_offers()` no seleccionaba `o.experience_min`, así que `offer.get("experience_min")` era siempre `None` → `req=0` → `years_match=1`. Fix: agregar `o.experience_min` al SELECT.

2. **Gap multiplier = 0.55** cegaba F_exp al 55% máximo. Con W_EXP=0.25, el score máximo teórico era 0.74, y ninguna oferta podía tener F_exp > 0.55. El gap no distinguía reconversión activa de inactividad real. Fix: gap eliminado de F_exp, pasa a ser contexto cualitativo exclusivo del HR LLM (ya estaba en el prompt de evaluate_hr).

3. **location_match = 0** por diseño (ADR-008). Implementado `compute_location_score()` determinista: remoto=1.0, híbrido=0.7, presencial misma ciudad=0.5, presencial fuera=0.2.

### Cambios en evaluate.py

| Línea | Antes | Después |
|-------|-------|---------|
| SELECT (get_pending_offers) | sin experience_min | `o.experience_min` añadido |
| compute_experience_score | `years_match * G(gap)` | `years_match` solo |
| run_evaluate → F_exp | `offer.get("experience_min"), candidate_years, employment_gap` | sin gap |
| _build_evaluation_params | `0` (hardcode) | `round(location_match * 100)` |
| save_evaluation | sin location_match | nuevo parámetro location_match |
| Nuevas funciones | — | `load_location_from_perfil`, `compute_location_score` |
| MONTH_NAMES | duplicados ene/es | merge sin duplicados |

### Efecto real en scores (T-5c)

Con candidate_years=4.3 y candidate_city="Jerez de la Frontera, Spain":
- avg score: 29.8 → 41.4 (efectivo: ~11.6 puntos de subida)
- 10 ofertas "Aplicar" (score 57–74), 51 "Con expectativas bajas" (35–54), 31 "No aplicar" (<35)
- F_exp ya no es el bottleneck — ahora M_core es el limitante (0.0 → máximo score 35)
- location_match funciona: 60 presencial → 20, 28 híbrido → 70, 4 teletrabajo → 100

## Zombie columns cleanup (junio 2026)

### Columnas eliminadas de offer_evaluations
7 columnas nunca pobladas tras el refactor determinista (commit 7a4709b):
- `education_match` (INTEGER) — LLM ya no devuelve score numérico
- `trajectory_coherence` (INTEGER, 0–15)
- `recency_relevance` (INTEGER, 0–15)
- `penalty` (INTEGER, 0–25)
- `company_fit_score` (INTEGER)
- `company_green_flags` (TEXT, JSON)
- `company_red_flags` (TEXT, JSON)

### penalty_breakdown → scoring_detail
Renombrada para reflejar que ahora almacena desglose de scoring v2
(M_core, M_sec, F_exp, F_fit, skill_detail) en vez de penalizaciones.

### Migración
- `migrate.py` añade función `drop_zombie_columns()` con ALTER TABLE
- `schema.sql` actualizado como fuente de verdad
- Tests raw INSERT actualizados para alinearse con schema actual
- `generate_dashboard.py`: SELECT sin zombies, scoring_detail aliased
- `save_evaluation()` params, _COLUMNS, _SET_CLAUSE sincronizados

### Pre-existing E402 en migrate.py
`load_dotenv()` antes de import desde src/db/init_db. Sin ruff config file
para per-file-ignores. No blocker: ruff format y tests pasan.

## Datos incompletos de Apify — TRAGSA / ATS custom (junio 2026)

- GRUPO TRAGSA (~12 ofertas) usa un ATS custom que no expone structured
  requirements (experience_min, education_level, etc.) a través del actor
  `easyapi/infojobs-job-scraper` de Apify.
- Consecuencia: `experience_min=0` y `education_level=NULL` en estas ofertas,
  causando que F_exp=1.0 (sin requisito de experiencia aparente) y que el LLM
  no tenga contexto estructurado de requisitos educativos.
- **No es un bug de nuestro código.** Es una limitación del scraping vía Apify.
  Las ofertas se incluyen igual pero con scoring basado solo en description_clean
  (el LLM puede detectar requisitos por texto libre si aparecen en la descripción).
- TRAGSA IDs en DB: 338, 343, 344, 345, 348, 351, 353, 354, 356, 357, 358, 359,
  360, 361, 362 (15 ofertas). Algunas con apply_block (titulación académica) porque
  el LLM lo detectó en la descripción; otras sin bloqueo porque el requisito solo
  está en los metadatos que Apify no capturó.
