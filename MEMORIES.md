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
