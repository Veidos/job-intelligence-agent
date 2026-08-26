# MEMORIES.md — Aprendizajes del Sistema

## Scrapling + capa bronze (ADR-023, ago-2026)

### Bloqueo Distil: expira solo
- El decoy de detail pages (200 OK "No podemos identificar tu navegador") duró ~8 semanas
- La constraint era reputación de IP, NO fingerprinting — Camoufox/stealth no la arreglan
- Tras enfriamiento, HTTP puro con warming sirve contenido real sin browser

### Patrón warming Distil (validado empíricamente)
- Secuencia: search primero (gana cookies) → dwell log-normal 8-45s → details con
  Referer de la búsqueda que los generó + Sec-Fetch-Site/Mode
- Las guías Imperva/Distil lo confirman: saltar frío a deep links = señal bot
- Coste: +0 requests extra (la búsqueda ya forma parte del pipeline)

### Scrapling como transporte
- FetcherSession(impersonate=chrome131): cookie jar persistente entre requests
- API: `sel.css()` devuelve `Selectors` indexable; `.attrib` dict; texto recursivo con
  `.get_all_text()` (`.text` solo captura nodos directos — trampa que costó un debug)
- Logging interno ruidoso → silenciar con `logging.getLogger("scrapling").setLevel(WARNING)`
- StealthySession requiere `scrapling install` (Chromium ~300MB); `install-deps` falla
  sin sudo pero no hace falta en este sistema
- Instalar scrapling[fetchers] ACTUALIZA curl_cffi compartido (0.15→0.16.2) — verificar
  suite completa tras instalar dependencias nuevas en el venv

### Capa bronze (scraper_raw_html)
- HTML original gzip nivel 9 (~88% ratio) + SHA-256 SIN comprimir, ANTES de parsear
- kind CHECK('search','detail'); search pages también se archivan (materia prima market_signals)
- Tabla aditiva IF NOT EXISTS; scraper_raw_responses.payload queda vivo en transición dual
- Lección re-aplicada: guardar SIEMPRE fuente primaria — jun-2026 pagó 21 re-scrapes por no tenerla
- Fixtures de tests = snapshots .gz de PoC; regenerables desde bronze sin requests

### Circuito anti-bloqueo (umbrales definidos)
- 2 decoys consecutivos → escalada stealth SOLO para details (~30s/unidad)
- Búsquedas siempre por HTTP barato incluso en modo stealth
- 8 fallos totales → ScraperBlockedError, run aborta limpio (sin hammering)

### Tests con engine compartido
- El row_factory del test_engine session-scoped puede cambiar a sqlite3.Row según qué
  tests corrieron antes → aserciones siempre por índice (`row[0]`), nunca tupla directa
- Inyectar fakes en ScraplingTransport exige setear AMBOS `_session` (ctx) Y `_client`

## Grammar constraints JSON vía Ollama format (ADR-024, ago-2026)

### Smoke test think×format
- `think=true` + `format=true` → **silencia traza think** completamente en gemma4:e4b
- Esto es comportamiento **pre-existente** desde junio, no es regressión
- `format=True` (bool) produce JSON crudo sin fences, misma velocidad (~23 tok/s)
- Razonamiento exigible vive en campos `required` del schema, no en la traza think

### Diseño de schemas
- Permisivo-en-contenido: strings libres, arrays sin minItems (respuestas variables)
- Estricto-en-estructura: tipos, enums, required fields
- Campos anulables con `null` REAL (type: ["string","null"]) — elimina clase del literal "null"
- "gemma4 nunca scores numéricos sin razonamiento" → reasoning/verdict en required

### GPU driver fix (ago-2026)
- Kernel module 580.159 vs userspace 580.173 → nvidia-smi NaN, Ollama CPU-only
- Fix: reboot after driver install (kernel module load requires restart)
- Post-reboot: driver 580.173.02, GPU detected, models offloaded correctly
- Benchmarks: qwen2.5:7b=36.1 tok/s (100% GPU), gemma4:e4b=23 tok/s (33% GPU)

### Pipeline E2E validado
- Run #34: 8 ofertas, 7 evaluadas, 3 Telegram, 0 JSON parse failures
- MAX_DETAILS_PER_SESSION=8 es bottleneck conocido — sin cap se espera ~40 detalles en ~14 min
- Lockfile 20h cooldown entre runs — OK para cron diario, no para pruebas inmediatas

## Configuración del proyecto
- Python 3.14+ requerido
- pytest instalado para tests
- Ollama ejecutándose localmente en http://localhost:11434
- gemma4:e4b como modelo principal (técnico + HR, temperaturas 0.1 y 0.0)
- qwen2.5:7b como MODEL_COMPANY para enriquecimiento de empresas (temperatura 0.0)
- qwen2.5-coder:7b eliminado como modelo de extracción técnica (no razonaba bien en contexto amplio)

## Suite de tests
- Estructura: tests/unit/ (funciones puras), tests/integration/ (DB + lógica)
- Fixture principal: `test_db` — temp file con schema.sql, rollback por test
- Fixture `test_conn` — wrapper sqlite3 compatible con save_evaluation
- Fixtures de datos: `sample_perfil_text`, `sample_offer`, `sample_offer_senior`, `sample_offer_no_exp`, `sample_offer_temporal`, `sample_offer_with_impossible_requirements`
- 231 tests: 203 originales + 20 dashboard server API + 6 fetch merge skills + 2 prev nuevos — todos passing
- Ollama cassettes: 13 JSON fixtures en tests/fixtures/ollama/ (no vcrpy)
- test_classifier_cassettes.py: usa test_engine (Connection) no test_db (Cursor) — role_classifier usa conn.cursor()
- test_evaluate_cassettes.py: cassettes directos (no wrapped), mock_ollama_call con side_effect para secuencias
- test_fetch_cassettes.py: call_args.kwargs para extraer prompt (no call_args[0][1])
- test_pipeline.py: flujo completo con stateful mocks (call_count++) para secuencias de llamadas
- ruff fix eliminó 6 imports sin usar de test_pipeline.py
- PLANS.md actualizado con 223 tests passing

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
- InfoJobs acepta `sinceDate` con valores `_24_HOURS`, `_7_DAYS`, `_15_DAYS`, `ANY`.
- `--since-date _24_HOURS` es el default tanto en `fetch.py` como en `run.py`.
- El valor viaja directo: CLI → `run_fetch(since_date=...)` → `build_search_urls()` → `&sinceDate=X`.
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
- `--skip-cv-check` salta el check pero ejecuta el pipeline (útil en nohup/headless)
- `.cv_hash` se guarda en raíz del proyecto (gitignored)
- **Lección:** el check fallaba en modo headless/nohup porque `sys.stdin.isatty()` es False y el CV tenía un falso positivo (hash distinto sin cambios reales). `--skip-cv-check` añadido para estos casos.
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

## Fetch en dos fases (refactor mayo/junio 2026)

### Era Apify (histórico, hasta ADR-016)
- `upsert_raw()` reemplazó a `upsert_offer()` para separar persistencia
  de Apify del enriquecimiento con LLM
- `raw_data` almacena el JSON completo del item Apify para re-enriquecimiento
- `enriched_at IS NULL` servía como flag de reintento automático

### Era scraper propio (ADR-016/017)
- `fetch.py` opera en 2 fases secuenciales:
  1. `persist_scraper_raw()` — guarda RawOfferDetail en `scraper_raw_responses` (append-only, UNIQUE offer_id)
  2. `_upsert_from_scraper_raw()` — lee raw pendientes, llama a `_upsert_offer_from_scraper()`
- Skills del `<dl>` "Conocimientos" van directamente a `core` — son requisitos estructurados
- `enriched_at` se setea en el mismo upsert (no hay Phase 3 separada)
- `role_level_label` eliminado del scoring — L es binario (presencia, no profundidad)
- `enrich_pending()` y `--enrich-only` eliminados (ADR-017)
- `level_multiplier()`, `LEVEL_ORDINAL`, `ROLE_LEVEL_TO_SKILL_LEVEL` eliminados de evaluate.py

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

## Enriquecimiento con think=True y num_ctx (mayo 2026) — HISTÓRICO

- En la era Apify, `extract_fields_with_llm` sin `think=True` fallaba en ~30% de ofertas
- Fix: `think=True` + `num_ctx=8192` → 92/92 ofertas enriquecidas
- **Desde ADR-017**: `extract_fields_with_llm()` ya no se llama desde el pipeline.
  El scraper proporciona todos los campos estructurados sin LLM.
- `ollama_call()` sigue aceptando `num_ctx` como parámetro (disponible para uso futuro)

## parse_salary — formato dict de Apify (mayo 2026)

- Apify actor `easyapi/infojobs-job-scraper` devuelve `salary` como dict estructurado:
  `{"range": {"min": 30000, "max": 33000}, "period": "YEAR", "currency": "EUR"}`
- `parse_salary()` acepta ahora ambos formatos: dict estructurado y string legacy
- Si es dict, extrae `range.min` y `range.max` directamente
- Si es string, aplica regex legacy

## fetch.py — argumentos CLI (mayo/junio 2026)

- `--max-items 0`: sin límite de resultados por keyword
- `--enrich-only`: **eliminado en ADR-017** (ya no hay enrich_pending que llamar)
- El scraper setea `enriched_at` en el upsert, no necesita reprocesamiento

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

## Flask Dashboard — Rediseño profesional (T-5g, junio 2026)

### Arquitectura (sin cambios desde T-5f)
- **Framework:** Flask (local, sin ORM, SQLite directo vía `sqlite3`)
- **SPA con Jinja2:** Backend sirve HTML+JS, datos vía fetch() desde 9 endpoints API REST.
- **Chart.js v4 vía CDN** para gráficos.
- **Static file serving:** `app.js` y `style.css` desde `src/dashboard/static/`.

### 4 Secciones (rediseño T-5g, ADR-015)
0 sections -> 4 sections with hierarchy:
1. **🔍 Ofertas** (default landing) — Tabla 9 columnas (Score, Título, Empresa, Modalidad, Publicado, Salario, Recomendación, Señal, Bloqueo). Sin M_core/M_sec/F_exp/F_fit. Modal con descripción colapsable + skills + breakdown scoring + sticky footer CTA.
2. **💼 Aplicaciones** — Lista con inline `<select>` de estado (applied/interviewing/offer/rejected/archived). Expandable card con notas/contacto/next_action_date. Botón "Ver oferta" → `openModal()`.
3. **🏢 Empresas** — Tabla + 2 charts (top 5 by offers, by sector)
4. **📊 Monitor** — Narrative: Resumen (KPIs) → Calidad de ofertas (score histogram) → Precisión del modelo (recomendación×relevancia, señal×recomendación) → Actividad (score trend + pipeline runs)

### Cambios clave del rediseño (T-5g vs T-5f)
| Aspecto | Antes (T-5f) | Después (T-5g) |
|---------|-------------|----------------|
| Landing page | 📊 Pipeline (monitor) | 🔍 Ofertas (exploración) |
| Navegación | 6 secciones planas | 4 secciones jerárquicas |
| Columnas tabla | 12 (incluye M_core, M_sec, F_exp, F_fit) | 10 (score, título, empresa, ubicación, modalidad, publicado, salario, recomendación, señal, bloqueo) |
| Modal footer | Vacío (scrolleabas hasta el final para guardar) | Sticky 2-state: "Añadir a aplicaciones" / "En aplicaciones · Ver →" |
| Descripción oferta | No disponible en modal | Collapsible `<details>` desde `description_clean` |
| Link InfoJobs | No disponible | Botón "Ver en InfoJobs" en modal |
| Aplicaciones | Timeline semanal CSS grid | Lista con estado inline `<select>` |
| Empresas | Solo tabla | Tabla + 2 charts |
| Monitor | Pipeline KPIs + Estadísticos + Runs (3 tabs separados) | Unificado en 1 sección con 4 subsections narrativas |
| Kanban | No existía | Explícitamente descartado (bajo volumen de apps) |
| filterBlocked | Por defecto activado (verde opresivo) | Por defecto desactivado (opt-in) |
| Fallback modal | Solo funcionaba si oferta estaba en OFFERS array | Fallback a APP_DATA desde Aplicaciones |

### Hotfixes post-T-5g (4 bugs en app.js, commit 6248c9c)

| # | Bug | Síntoma | Causa raíz | Fix |
|---|-----|---------|------------|-----|
| 1 | **Fechas NaN** | `Publicado: NaN undefined NaN` | `dateFmt(d + 'Z')` duplicaba `Z` cuando `published_at` ya termina en `Z` → `Invalid Date` | Helper `_parseDate()` que normaliza formato: `s.replace(' ', 'T')` + solo añade `Z` si no termina ya. Afectaba `dateFmt()`, `fullDate()`, sort por fecha, y chart score trend. |
| 2 | **Skills "Undefined"** | `Skills (undefined)`, luego `Sin datos de skills` aunque hay 92 ofertas con skills | `skill_detail` en DB es objeto `{core: [...], secondary: [...]}`, no array. `sd.skill_detail \|\| []` devuelve el objeto (truthy) → `.length` es `undefined` | Normalizar con `Object.entries(skill_detail)` → `skillCats` (categorías con label `"Core"`/`"Secundarias"`) + `totalSkills` con `reduce`. Template itera categorías con fila `.skill-cat` + items anidados. |
| 3 | **Modal fallback crash** | `Error al cargar detalle` al abrir oferta desde Aplicaciones | `Object.assign(d, o)` unconditional pisoteaba `d.strengths` (array JS) con `o.strengths` (JSON string SQL). Luego `d.strengths.map()` → `TypeError`. | Merge condicional: solo cuando `!d.salary_display` (fallback desde APP_DATA), y parsea `['strengths','hr_concerns','red_flags','interview_prep']` de string a array. |
| 4 | **Runs vacío sin mensaje** | Tabla vacía con puras rayas | `/api/runs` devuelve `[]` (0 registros en DB), template no contemplaba este caso | `if (!data.length)` → mostrar `<tr><td colspan="7" class="empty">Sin ejecuciones registradas</td></tr>` |

**Lección aprendida (skills):** `generate_dashboard.py` (legacy) iteraba `Object.keys(sd).forEach(cat => ...)` y funcionaba correctamente. Al reescribir app.js para T-5g, se asumió que `skill_detail` era un array (como en otros proyectos similares), pero la DB almacena un objeto categorizado. El old dashboard manejaba esto; el nuevo no — hasta ahora.

### Segunda ronda de hotfixes (app.js, commits 6274985..9de94e7)

| # | Bug | Síntoma | Causa raíz | Fix | Commit |
|---|-----|---------|------------|-----|--------|
| 5 | **Save modal sin error handling** | Botón "Añadir a aplicaciones" se quedaba en "Guardando..." o no cambiaba — usuario no sabía si se guardó | `saveApplication()` sin `.catch()` — si `fetch` o `r.json()` fallaban, el error se tragaba en silencio | Añadir `r.ok` validation + `.catch()` que restaura el botón y loggea el error a console | `6274985` |
| 6 | **Footer vacío pre-fetch** | Botón de guardar nunca aparecía si el fetch a `/api/offers/<id>` tardaba o fallaba | `$('modalFooter').innerHTML = ''` borraba el footer; el botón se renderizaba solo en el `.then()` del fetch | Footer con botón INMEDIATO mediante `data-offer-id` antes del fetch. Fetch solo actualiza a estado "saved" vía `outerHTML`. Click handler migrado de inline `onclick` a `addEventListener` delegado en `modalFooter` | `4043451` |
| 7 | **saveAppDetails status stale** | Cambiar estado en `<select>` (Applied→Interviewing) y luego pulsar Guardar sobrescribía el cambio con el estado viejo | `saveAppDetails()` enviaba `status: a.status` (APP_DATA cacheado) en vez del valor actual del `<select>` | Añadir `id="appStatus${a.id}"` al `<select>`. `saveAppDetails(id, btn)` lee `statusEl.value` del DOM. Feedback visual con 3 estados: Guardando... → ✓ Guardado (verde, 2s) / Error (rojo, 2s). Incluye `r.ok` validation + `.catch()` | `8340c5f` |
| 8 | **Confirm delete confuso** | "¿Eliminar esta aplicación?" sugería que se borraba la oferta entera, no solo el seguimiento | Mensaje ambiguo — el usuario no distinguía entre `DELETE FROM applications` (tracking) y borrar la oferta | "¿Eliminar este seguimiento? La oferta no se perderá." | `be1507b` |
| 9 | **Charts descentrados** | Top 5 horizontal: barras desplazadas a la derecha por etiquetas largas (ej. "Etalentum Selección"). Sector doughnut: leyenda apelotonada abajo | Sin `layout.padding` en el bar chart. `position: 'bottom'` comprime etiquetas si hay muchos sectores | `maintainAspectRatio: false` + `layout.padding: { left:10, right:20 }` en bar chart horizontal. Legend `position: 'right'` en doughnut de sectores | `9de94e7` |

**Principio establecido (#6):** El botón de acción principal nunca debe depender de un fetch para renderizarse. El `offer_id` ya está disponible localmente en `OFFERS`. El footer con el botón se renderiza sincrónicamente; el fetch solo actualiza el estado (saved/unsaved).

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

## Dashboard enrichment — KPIs nuevos (T-5h Fase 1, junio 2026)

### Restricción rota: "Sin server.py"
- HANDOFF.md exigía "solo frontend" pero `skill_detail` no se exponía en `/api/offers`
- Solución: +3 campos en el dict (`salary_min`, `salary_max`, `skill_detail`) — payload adicional negligible para localhost
- Lección: la regla "sin server.py" era válida para branding/microcopy pero no para KPIs que necesitan datos estructurados que el endpoint ya consulta pero descarta

### Decisiones técnicas
- `s.skill || s.name` — skills pueden venir con cualquiera de los dos campos, el modal builder ya lo manejaba pero la nueva función de agregación no
- `v == null` en salary dist — `!v` filtra salary=0 (falsy en JS), necesario null check explícito
- Sparkline con `responsive: false` + `width/height` explícito en CSS + canvas — Chart.js no infiere tamaño sin contenedor con dimensiones

### Patrón para nuevos charts
- Seguir `destroyChart()` + `charts[name] = new Chart(...)` — evitar memory leaks
- `if (!data.length) return` check antes de crear chart
- Títulos descriptivos en español en los charts (no confiar solo en tooltips)

### Skills split por categoría (hotfix junio 2026)
- `skill_detail` en BD es `{"core": [...], "secondary": [...]}` — **no hay campo `category`** en cada skill
- `computeSkillsData()` original aplanaba ambos arrays con `Object.values(sd).flat()` → "Master Oficial" aparecía en core y secondary, duplicando frecuencia y contaminando el top
- Fix: iterar `sd.core` y `sd.secondary` por separado → 3 charts: Core (técnicos), Secondary (soft/requisitos), Gap (solo core, accionable)
- Stacked bar ciudad×modalidad: más informativo que bar simple de ciudades o doughnut de modalidad. Un chart responde "cuántas ofertas hay en Madrid y de qué tipo"
- Todos los charts del dashboard son ahora barras (0 doughnuts). Consistencia visual > variedad de tipos

### Ubicación como columna en tabla de Ofertas
- `city` ya estaba en `/api/offers` endpoint pero no se mostraba en la tabla
- Añadir columna Ubicación (entre Empresa y Modalidad) fue 1 th + 1 td + sort handler
- Sin cambios en server.py — el dato ya viajaba en la respuesta

## Promise.all async bug en dashboard (junio 2026)

- `loadStats()` y `loadOffers()` en `app.js` hacían `fetch()` pero **no devolvían la promesa**.
- `Promise.all([loadStats(), loadOffers()])` recibía `[undefined, undefined]`, resolvía
  instantáneamente, y el doughnut chart del Pipeline se creaba con `DATA = []` → `[0,0,0]`.
- Fix: añadir `return` antes de cada `fetch()`. El gráfico apareció al recibir datos reales.
- Lección: toda función async que se use en `Promise.all` debe hacer `return` de la promesa.

## Bug: fetch_company keys en run.py (junio 2026)

- `run.py:run_pipeline()` loggeaba `enrich_result["new"]` y `enrich_result["updated"]`, pero `fetch_company.run()` devuelve `{enriched, linked, skipped, errors, pending}`.
- El error quedaba silenciado por el `except Exception`.
- Fix: cambiar las keys en el log a `enriched`, `linked`, `errors`, `pending`.

## search_runs persistence (junio 2026)

- `run_pipeline()` nunca escribía en `search_runs` — la tabla existía pero vacía.
- Añadidas `_start_run()` y `_persist_run()` en `run.py`:
  - Captura `query_params` (args en JSON), `offers_fetched`, `new_offers`, `evaluated`, `errors`, `duration_ms`, `status`
  - Errores de pasos individuales se acumulan sin detener el pipeline
  - `_persist_run()` recibe todos los parámetros explícitamente (no usa closures)

## Limitaciones de Apify (ADR-016)
- El actor `alvaraaz/infojobs-actor` solo extrae campos básicos: code, title, description, city, link, contractType, workday, teleworking, publishedAt, companyName, companyLink
- **No extrae** la sección estructurada "Requisitos" de InfoJobs (estudios mínimos, experiencia mínima, idiomas requeridos, conocimientos necesarios, sector)
- La descripción libre NO contiene los datos estructurados de requisitos
- `experience_min` inferido por LLM desde descripción → suele dar 0 cuando el valor real es mayor
- Skills extraídas por gemma4 desde la descripción son muy pocas (1-2) y genéricas, porque el prompt limita a "3-5 skills" pero el LLM se queda corto
- Consecuencia: scores inflados porque M_core/M_sec se calculan sobre muy pocas skills
- **Solución:** scraper propio con curl_cffi + BeautifulSoup que parsea el HTML de la oferta individual y extrae todos los campos estructurados (ADR-016)

## Custom scraper con curl_cffi (junio 2026)

### TLS fingerprint bypass
- InfoJobs usa JA3 fingerprinting → `requests` es bloqueado (`curl_cffi` lo evita)
- `curl_cffi.Session(impersonate="chrome124")` funciona tanto para search como detail pages
- No hay JS challenge más allá del fingerprinting — las páginas son server-rendered (React SSR híbrido)
- Constructor `Session(impersonate="chrome124")` acepta impersonate en kwargs (no como argumento posicional)

### HTML structure hallazgos
- **Search page:** cards de oferta en `li.ij-OfferList-offerCardItem`, publicidad se filtra por `aria-label="Publicidad"` (atributo de accesibilidad, legalmente requerido → más estable que clases CSS)
- **Detail page:** header items en `.ij-OfferDetailHeader-detailsList-item p.ij-BaseTypography`, identificados por heurística de texto (los SVG no tienen atributos semánticos de identificación)
- **Requisitos:** sección `<dl>` después de `<h3>` con texto "Requisitos". Cada `<dt>` es un label, el `<dd>` contiene el valor. No todos los labels están presentes en todas las ofertas.
- **Publicación:** InfoJobs NO usa `time[datetime]` ISO. Es texto plano ("Publicada Hace 4d", "29 may", "Hoy", "Ayer"). `_extract_published_at()` parsea 5 formatos con `[data-testid='sincedate-tag']` o `.ij-FormatterSincedate`.

### Bugs de parseo encontrados durante TDD
1. **`"no" in text` para experiencia:** `"Al menos 4 años"` contiene "menos" → `"no" in "menos"` es `True`. Fix: usar `re.search(r"\bno\b", text.lower())` (word boundary)
2. **City regex con multi-word:** "A Coruña (A Coruña)" requiere espacio en el nombre de ciudad. Fix: `(?:\s[A-ZÁÉÍÓÚÑ][a-záéíóúñÀ-ÿ]+)*` (asterisco, no +, para ciudades de 1 palabra como "Barcelona")
3. **Search card title:** El `<a>` con clase `ij-OfferCardContent-description-link` tiene el texto del título pero `title` attribute vacío. Usar `get_text(strip=True)` no `.get("title")`.

### Bugs de parseo post-producción (corregidos en producción)
1. **Skills duplicados** — `_parse_skills()` devolvía cada skill dos veces por anidamiento `<li>`/`<span>` (li contiene span, el parser iteraba ambos). Fix: `list(dict.fromkeys(skills))`.
2. **Descripciones vacías** — `_parse_description()` usaba `[class*='description']` que capturaba el toggle "Ofertas similares" (27 chars) en vez del bloque de descripción real. **Todas las 21 ofertas del scraper** tenían `description_clean` inválida. Fix: selectores semánticos (`section.ij-OfferDetailPage-mainContent`, `.ij-OfferDetailDescription`) + guard `len(text) > 100`. Las 21 ofertas se re-scrapearon con `scraper_lab/reparse_offers.py`.
3. **`published_at` nulo** — Asumir `time[datetime]` era incorrecto. InfoJobs usa texto relativo. Fix: `_extract_published_at()` con 5 formatos: "Hace Xd", "Hace Xh", "Hoy", "Ayer", "DD de mes" (ej. "29 de may"). Backfill de 43/44 ofertas con `scraper_lab/fix_published_at.py` (1 expirada sin fecha).

### Otros aprendizajes de la sesión de bugfixes
- **`--since-date` era no-op**: el scraper ignoraba el parámetro. Fix: `InfoJobsScraper.search()` ahora acepta `since_date` y lo pasa como `sinceDate` en la URL (`_24_HOURS`, `_7_DAYS`, `_15_DAYS`, `ANY`).
- **`build_search_urls()` eliminado**: código muerto de la era Apify, nunca llamado por el scraper. Sus tests también eliminados.
- **Test count**: 204 → 197 (tras eliminar `build_search_urls`) → 203 (6 nuevos de `published_at`).
- **`description` selector**: `section.ij-OfferDetailPage-mainContent` captura el panel completo (requisitos + descripción). Es el selector más estable; no hay contenedor semántico que separe solo la descripción.
- **`fix_published_at.py`**: script one-shot en `scraper_lab/` que backfillea `published_at` parseando el texto plano guardado en `scraper_raw_responses.payload` (evita re-scrapear).
- **43 scraper offers** en DB con `published_at` poblado, 44 filas en `scraper_raw_responses`, 1 oferta expirada eliminada.

### Patrón de tests
- Snapshots HTML reales guardados en `scraper_lab/snapshots/`
- Tests unitarios separados por perfil de oferta: `TestParseDetailBeca` vs `TestParseDetailSenior`
- Cada test verifica un campo específico, no el objeto completo — facilita debugging
- TDD: los tests contra snapshots reales se escribieron antes de implementar los parsers

## Eliminación de Phase 3 enrich_pending y role_level_label (ADR-017, junio 2026)

### Decisión
- `enrich_pending()` eliminado — el scraper proporciona todos los campos estructurados
- Skills del `<dl>` "Conocimientos" van directamente a `core` en `_upsert_offer_from_scraper()`
- `enriched_at` se setea en el upsert (INSERT y UPDATE), no en una fase separada
- `role_level_label` eliminado del scoring — `L_i` es binario (1.0 si presente, 0.0 si no)
- `level_multiplier()`, `LEVEL_ORDINAL`, `ROLE_LEVEL_TO_SKILL_LEVEL` eliminados (código muerto)

### Datos que validaron la decisión
- `experience_min` del scraper coincidía al 100% con el LLM (22 ofertas scraper verificadas)
- `role_level_label` era 67% "mid" — proxy ruidoso cuando `experience_min_years` está disponible
- 0 skills en DB tenían `level_required` explícito (todas dependían del default)
- `enrich_pending()` era ~120 líneas que llamaban a gemma4 para campos que el scraper ya daba

### Pipeline actual (2 fases en fetch)
1. `persist_scraper_raw` — guarda RawOfferDetail en scraper_raw_responses (append-only)
2. `_upsert_from_scraper_raw` — upsert en offers con skills en core + enriched_at

### Impacto en scores
- `M_core` sube: skills presentes ya no penalizan por nivel (antes mid → 0.5, ahora 1.0)
- `M_sec` = 0 para ofertas sin skills en secondary (peso 0.15, aceptable)
- `F_exp` sin cambios (sigue usando `experience_min_years` del scraper)
- `F_fit` sin cambios (HR LLM inalterado)
- Ofertas senior son las más beneficiadas (antes L=0.33, ahora L=1.0)

### Lecciones aprendidas
- Validar con datos reales antes de diseñar sustitutos: eliminar el proxy ruidoso
  (role_level_label) y medir el impacto real fue mejor que diseñar un reemplazo
  determinista especulativo
- Cuando el scraper proporciona datos estructurados, el LLM enrichment es
  redundante si COALESCE preserva los valores del scraper
- `extract_fields_with_llm()` se conserva como función utilidad para casos
  futuros donde se necesite extracción desde descripción libre

## Sesión de fixes de calidad (junio 2026)

### SQL injection en server.py
- `LIMIT` se interpolaba con f-string: `f" LIMIT {limit}"`
- Aunque `limit` se casteaba a `int`, la práctica correcta es usar `" LIMIT ?"` con `params.append(limit)`
- Fix: parámetro posicional en lugar de interpolación

### F-string logging en role_classifier.py
- 11 instancias de `logger.info(f"...")` en vez de `logger.info("... %s", var)`
- El resto del proyecto ya usaba lazy `%s` — role_classifier.py era el outlier
- Fix: todas convertidas a lazy formatting

### DB_PATH inconsistente
- `role_classifier.py` tenía `DB_PATH` hardcodeado a nivel de módulo, pero `run_classifier()` usaba `os.getenv("DB_PATH", "data/jobs.db")`
- `_run_logic()` abría conexión con el path hardcodeado, `run_classifier()` abría su propia conexión para COUNT
- Fix: eliminar `DB_PATH`, usar `get_connection()` de `init_db.py` que ya maneja el env var

### Tests con IDs hardcodeados
- 3 tests asumían que los IDs de autoincrement empezaban en 1: `offer_id IN (1)`, `offer_id IN (1, 2)`, `offer_id = 1`
- Esto funcionaba solo por orden de colección de pytest (archivos anteriores se ejecutaban primero)
- Al añadir `test_dashboard_server.py` (orden alfabético temprano), los IDs cambiaban
- Fix: usar JOIN por `source_id` o lookup dinámico en lugar de IDs hardcodeados
- Lección: **nunca asumir valores de autoincrement en tests** — usar SELECT por campo único

### Tests de dashboard
- 18 tests que verifican todos los endpoints REST del servidor Flask
- Usan monkeypatch de `get_connection` con wrapper que ignora `close()` para preservar la conexión session-scoped
- Validan: stats, offers con/sin filtros, 404, companies, applications CRUD, feedback CRUD, runs, HTML serve, static files, favicon

## Employer ID desde scraper propio (ADR-018, junio 2026)

### RawOfferDetail.employer_id
- `employer_id` se extrae desde el company link en el HTML de detalle (`em-i{HASH}`)
- `_extract_employer_id()` busca selectores del company logo area, extrae href y parsea con regex `r"/em-i([a-zA-Z0-9_]+)"`
- Se persiste en `_upsert_offer_from_scraper()` tanto en INSERT como en UPDATE con `COALESCE`
- `fetch_company.py` ya usaba `employer_id` como `infojobs_company_id` — no hay conflicto. El scraper popularlo mejora el enrich porque más ofertas tendrán ID real.

### CandidateProfile en src/utils/
- `CandidateProfile.from_perfil()` hace parseo en 1 pass con regex por sección (`re.DOTALL | re.IGNORECASE`, lookahead `(?=\n##|\Z)`)
- `perfil_sections: dict[str, str]` preserva cada sección completa para recomposición vía `excerpt()`
- Elimina truncado posicional (`perfil[:2500]`) que podía cortar `personal_concerns`
- `personal_concerns` ahora SIEMPRE llega al HR LLM
- `raw_perfil` preservado con `# TODO: eliminar` para migración gradual
- `excerpt()` omite secciones faltantes silenciosamente (log DEBUG), no hace KeyError

### Prioridad inversa en extracción de descripción
- `_extract_relevant_description()` busca marcadores de requisitos y da prioridad al bloque de requisitos (hasta 1000 chars) sobre el intro (resto hasta 2000)
- El clasificador recibe la señal más densa primero
- Marcadores: "requisitos", "se requiere", "se necesita", "buscamos", "formación", "estudios mínimos", "experiencia mínima"

### LLM quality metrics
- 3 contadores en `ollama_client.py`: `calls`, `json_parse_failures`, `empty_responses`
- In-memory, no persistidos en DB — son señal de runtime
- `get_llm_metrics()` se loggea al final del pipeline en `run.py`
- `null_fields` no se cuenta — es responsabilidad del caller, no de `ollama_call()`

### location_match como columna informativa
- No se pondera en el score final (status quo)
- `F_fit` del HR LLM ya captura ubicación cualitativamente
- El usuario evalúa caso por caso en el dashboard

## Dashboard UI fixes (junio 2026)

### Runs table movida a Pipeline
- La tabla detallada de ejecuciones del pipeline (`/api/runs`) estaba en Monitor
  colapsada bajo `<details>`. No es intuitivo — Monitor muestra KPIs/gráficas, no
  ejecuciones. Pipeline es el lugar natural.
- Movida a Pipeline como segundo desplegable "Detalle de ejecuciones", junto al
  ya existente "Resumen por ejecución" (que usa `/api/pipeline-runs`).
- `loadRuns()` movida de la sección Monitor a la sección Pipeline en app.js.

### Doughnut tooltip con porcentaje
- El doughnut de "Empresas por sector" mostraba números crudos en tooltip.
- Chart.js tooltip `callbacks.label` ahora calcula el total del dataset y muestra
  "Tecnología: 12 (32.4%)". Sin dependencias externas, solo un callback.
- Patrón: `const total = ctx.dataset.data.reduce((a, b) => a + b, 0); const pct = ((ctx.parsed / total) * 100).toFixed(1);`

### Filtros consistentes con "Ocultar..."
- Tres filtros checkbox en el dashboard: dos usaban "Ocultar..." (aplicadas,
  >30 días) y uno usaba "Mostrar..." (bloqueadas). Inconsistencia UX.
- Solución: renombrar a "Ocultar bloqueadas", invertir la lógica JS
  (`const showBlocked = !$('filterBlocked').checked`), y marcar `checked` por
  defecto. Los 3 filtros ahora usan la misma convención semántica.
- Lección: los filtros checkbox deben seguir una misma convención semántica.
  Mezclar "Mostrar X" y "Ocultar Y" confunde al usuario. Elegir una (Ocultar)
  y mantenerla.

## Post-merge scraper core — ADR-021 (junio 2026)

### Decisión
- `extract_fields_with_llm()` clasifica skills desde la descripción libre, pero
  skills del `<dl>` de InfoJobs ("Conocimientos") son requisitos explícitos del
  empleador → el LLM no tiene autoridad para reclasificarlas como secondary.
- `_merge_scraper_skills_into_llm()` aplica post-merge determinista tras el LLM.
- 3 reglas: (1) skill del scraper en LLM secondary → mover a core,
  (2) skill del scraper ausente en LLM → añadir a core,
  (3) secondary del LLM sin match → conservar.

### Normalización
- Match exacto case-insensitive es frágil: "Power BI" vs "PowerBI",
  "Scikit-learn" vs "sklearn", "Entity Framework" vs "EntityFramework".
- Solución: `re.sub(r"[\s\-_./]", "", name.strip().lower())` — elimina
  espacios, guiones, underscores, puntos y slashes antes del match.
- El nombre que persiste en core es siempre el del scraper (`original_name`
  del dict `scraper_normalized`), no la versión del LLM. Esto evita duplicados
  con nombre LLM distinto al scraper.
- La normalización solo se usa para el match interno; los nombres originales
  del scraper se preservan.

### Tests
- 6 casos en `test_fetch_merge_skills.py`:
  - Caso 1: Entity Framework en secondary LLM → core con nombre scraper
  - Caso 2: Docker ausente en LLM → añadido a core
  - Caso 3: Secondary Tableau sin match → conservado
  - Caso 4: Scraper vacío → respetar LLM
  - Caso 5: LLM vacío → fallback a scraper en core
  - Caso 6: Normalización "Power BI" vs "PowerBI"

### Lecciones
- No confiar en el LLM para clasificar skills que ya vienen clasificadas
  por la fuente original (el `<dl>` del HTML). El LLM es útil para descubrir
  skills en texto libre, pero no para reclasificar datos estructurados.
- La normalización antes del match es un patrón reusable para cualquier
  comparación entre dos fuentes con formatos divergentes (scraper vs LLM,
  API vs DB, etc.).
- Si el LLM devuelve `{}` o `skills_required` vacío, el fallback
  `base_skills` ya pone todo en core — el merge es redundante pero no daña.
- 225 → 231 tests.

## Sesión 2026-06-15 — Borrón y cuenta nueva + fixes de pipeline

### Scraper 403 Forbidden — Rate limiting
- InfoJobs bloqueó **todas** las detail pages de "Ingeniero de Procesos" con 403 usando delay 2.0 fijo
- Fix dual: delay 2.0→4.0s + jitter aleatorio 0-2.0s + fingerprint rotatorio (chrome131/safari17/chrome124)
- Resultado: 0 errores 403 en el re-run con 79 detail fetches
- Lección: delay fijo es detectable como patrón de bot. Jitter rompe el patrón.

### `--dry-run` no protegía fetch.py
- `run_fetch_scraper()` no aceptaba `dry_run` — escribía en DB aunque run.py pasara `--dry-run`
- El timeout de la dry-run dejó 36 filas huérfanas en `scraper_raw_responses` con un `run_id` que ya nunca se procesaría
- Fix: `run_fetch_scraper()` ahora acepta `dry_run=True` y salta persistencia

### `_upsert_from_scraper_raw()` filtraba por `run_id`
- `WHERE run_id = ? AND processed = 0` → si un run aborta, filas huérfanas
- Fix: `WHERE processed = 0` — procesa todas las pendientes independientemente del run_id
- Especialmente importante para pipelines con reinicios frecuentes

### `LIMIT 0` en SQLite
- `LIMIT 0` devuelve 0 filas en SQLite, no es "sin límite"
- `-1` es el equivalente SQLite de "sin límite"
- Mismo problema con list slicing `[:0]` en Python: lista vacía
- Lección: cada función destino debe normalizar `limit=0` → `-1`/`None` internamente (patrón role_classifier)

### `published_at` nulo en ofertas scrapeadas
- InfoJobs puede tener texto atípico: "Publicada hace 3d. Publicada de nuevo" que no matchea los 5 formatos del parser
- Fallback: `scraped_at` como `published_at` — error de 1 día irrelevante para ciclado de 30 días
- Sin fallback, ofertas sin fecha nunca expiran del dashboard

### Dashboard — Verificación post-reset
- Zombie columns eliminadas (7 columnas de offer_evaluations) — ninguna referenciada en dashboard
- `skill_detail` como objeto categorizado (no array) — dashboard lo maneja correctamente
- Pipeline completo verificado: 65 ofertas, 176 companies, 65 evaluaciones, todas las APIs respondiendo

### Dashboard — Bug filtro modalidad + normalización canónica (junio 2026)
- **Bug 1:** `!allowedMoves.includes(d.work_mode)` sin guardia para `""` → 6 ofertas sin modalidad invisibles
- **Bug 2:** `workModeValue("Teletrabajo")` devolvía `"Teletrabajo"` (no normalizado) → el filtro por `includes()` no matcheaba `"Solo teletrabajo"` en `allowedModes` → 2 ofertas con esta variante del scraper invisibles
- **Bug 3:** `workModeLabel("Teletrabajo")` y `workModeLabel("")` creaban categorías `"Teletrabajo"` y `"-"` en el chart de modalidad
- **Causa raíz:** fragmentación de la normalización — `workModeLabel()` y `workModeValue()` tenían mapas paralelos e incompletos. El scraper produce 4 variantes: `Presencial`, `Híbrido`, `Solo teletrabajo`, `Teletrabajo` (sin "Solo") y vacío. El frontend solo mapeaba 3.
- **Fix estructural:** constante canónica única `WORK_MODE_CANONICAL` que mapea las 4 variantes del scraper a 3 categorías normalizadas: `Remoto`, `Híbrido`, `Presencial`. `workModeLabel()`, `workModeValue()` y el chart consumen el mismo mapa.
- **Lección:** cuando un valor de dominio viene de múltiples fuentes (scraper/API/input), la normalización debe vivir en un único punto canónico. Si el scraper añade una variante nueva, solo hay que tocar `WORK_MODE_CANONICAL`. El filtro usa `workModeValue(d.work_mode)` para comparar contra `allowedModes` (que ya emite valores normalizados).

## Sesión 2026-06-18 — 13 ítems del análisis intensivo

### Console handler duplicado
- `setup_logging()` protegía con `if root.handlers: return`, pero `run_pipeline()` añadía un `StreamHandler` incondicionalmente fuera de esa función.
- Fix: mover el `StreamHandler` dentro de `setup_logging()`, protegido por la misma guardia.
- Lección: nunca añadir handlers de logging fuera de la función de setup que tiene la guardia.

### Autenticación Telegram (decorador en bot.py)
- La validación de `user_id` debe vivir en la capa de transporte (bot.py), no en la capa de datos (handlers.py).
- Patrón establecido: `require_auth` decorator con `@wraps` que protege todos los handlers públicos.
- `feedback_handler` (helper interno llamado por f1/f2/f3) no se decora directamente — ya está protegido por los handlers que lo llaman.
- `ALLOWED_USER_ID` = 0 (default) desactiva la autenticación, manteniendo compatibilidad con instalaciones existentes.

### sys.path.insert en módulos instalables
- `bot.py` tenía `sys.path.insert(0, ...)` a nivel de módulo para poder importar `src.*`.
- El proyecto es un paquete instalable (`pip install -e .` via pyproject.toml) — las importaciones absolutas funcionan sin sys.path.
- Fix: eliminar `sys.path.insert` y los `# noqa: E402` asociados.
- Lección: si el proyecto tiene pyproject.toml con `pip install -e .` como método oficial de instalación, ningún módulo necesita `sys.path.insert`.

### run_fetch_scraper() retorna dict
- Cambiar de `int` a `dict` (`{"new": ..., "total": ...}`) en lugar de tuple es más extensible.
- Permite añadir más métricas en el futuro sin romper callers.
- `_persist_run()` ahora usa `offers_fetched = total_raw` (total scrapeado) y `new_offers = new_count` (solo inserciones), que era el diseño original del schema.

### try/finally en conexiones DB
- Patrón: `conn = get_connection()` → `try:` → operaciones → `finally: conn.close()`
- Aplica a: `models.py:get_user_settings()`, `handlers.py:get_latest_daily_offers()`, `send.py:get_top_offers()`, `send.py:save_feedback()`.
- `handlers.py:save_feedback()` ya usaba try/finally correctamente — es la excepción, no la regla.

### Commit por fila en scraper raw
- `_upsert_from_scraper_raw()` hacía un solo `conn.commit()` al final del batch.
- Si una iteración fallaba (ej. payload corrupto), las filas anteriores con `processed=1` quedaban sin commitar.
- Fix: `conn.commit()` por iteración exitosa y por iteración con error.
- Lección: batch commits son frágiles cuando cada fila debe persistir su estado individualmente.

### Truncado JSON seguro
- `json.dumps(item, ...)[:3000]` podía cortar el JSON a mitad, generando respuestas LLM inconsistentes.
- Fix: truncar solo `item["description"]` antes de serializar, preservando la integridad del JSON.
- Patrón: `desc = item.get("description", "")[:2800]` → `safe_item = {**item, "description": desc}`.

### Acentos en compute_location_score
- `candidate_city.lower() in offer_city.lower()` no normalizaba acentos: "Málaga" ≠ "Malaga".
- Fix: `unicodedata.normalize("NFD", s.lower())` elimina diacríticos antes de la comparación.
- Helper local `_norm()` definido dentro de `compute_location_score()` para mantener el scope.

### Columnas zombie role_level / role_level_label
- Ningún código las escribe (role_classifier.py no, fetch.py no, scraper no).
- Decisiones: ADR-017 eliminó role_level_label del scoring; el scraper no necesita role_level.
- Fix: `drop_offers_zombie_columns()` en migrate.py con SQLite 3.46.1 (soporta DROP COLUMN desde 3.35.0).
- Guardia `if col exists` para ser seguro en re-ejecución de migración.

### threading.Lock para métricas globales
- `_metrics` dict en ollama_client.py es mutable y compartido.
- Fix: `threading.Lock` + helper `_inc_metric()` en lugar de `_metrics[key] += 1` directo.
- No crítico en el scope actual (single-thread), pero previene race conditions futuras.

## Anti-bot hardening del scraper (2026-06-29, ADR-022)

### Sleep log-normal
- `random.lognormvariate(mu=2.5, sigma=0.6)` con clamp [8, 45]s.
- Mediana ~12s, media ~15s. Simula pausa de lectura humana real.
- No usar delay fijo ni uniform distribution — son detectables como patrón de bot.
- El sleep anterior (delay=4.0 + random.uniform(0, 2.0)) fue bloqueado por Distil Networks.

### Lockfile 20h entre runs
- `data/.last_infojobs_run` guarda timestamp del último fetch exitoso.
- `try/except (ValueError, OSError)` protege contra archivo corrupto o vacío.
- Solo se escribe si `total_raw > 0` (fetch con resultados, no dry-run).
- Compatible con cron diario (9:00).

### MAX_DETAILS_PER_SESSION = 8
- Límite en `fetch.py`, no en `search()`. Los stubs de búsqueda se recolectan completos
  (son baratos, ~1 request por keyword). Solo los primeros 8 details se fetchean.
- Los stubs restantes se descartan — se recuperarán en el siguiente run (lockfile respeta 20h).

### Dedup intra-run
- `seen_ids: set[str]` antes del loop de details en `fetch.py`.
- InfoJobs muestra la misma oferta como resultado orgánico + promoted en la misma página.
- El `INSERT OR IGNORE` en DB maneja el duplicado, pero el dedup evita gastar un slot de los 8.

### City fallback desde URL
- `_city_from_url()` extrae ciudad del slug de la URL (`/barcelona/` → `"Barcelona"`).
- Sin request extra, sin tocar el selector CSS fallido.
- Regex: `infojobs\.net/([^/]+)/`, `.replace("-", " ").title()`.

### Perfiles curl_cffi 0.15.0
- Solo Chromium en Linux: chrome131, chrome124, chrome120, chrome119.
- Edge 101 es válido (Edge Linux existe en entornos dev/corporativos).
- Safari eliminado: fingerprint TLS Safari desde IP con historial Chrome es señal de
  inconsistencia para Distil Networks.
- Verificar perfiles con: `python -c "from curl_cffi.requests import BrowserType; print([e.value for e in BrowserType])"`.

### Headers reales en detail requests
- `Referer: search_url` (URL de búsqueda que generó el stub).
- `Sec-Fetch-Site: same-origin` + `Sec-Fetch-Mode: navigate`.
- `_fetch()` acepta `headers: dict | None`.

### Camoufox descartado por IP estática
- Camoufox mitiga fingerprinting TLS/HTTP2 pero no la correlación por IP.
- Con IP estática, Distil correlaciona todas las sesiones independientemente del fingerprint.
- Si la IP queda bloqueada: proxy residencial rotatorio, no Camoufox.
