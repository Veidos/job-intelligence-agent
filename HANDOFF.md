# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-11
**Fase activa:** Sesión de evaluación y fixes de calidad.

## Cambios de la sesión actual (2026-06-11)

### server.py — SQL injection fix
- `LIMIT ?` con parámetro en vez de `f" LIMIT {limit}"` (riesgo bajo, limit ya era int)

### role_classifier.py — Logging lazy, DB_PATH unificado
- 11 f-string logging → lazy `%s` formatting
- `DB_PATH` hardcodeado eliminado, ahora usa `get_connection()` de `init_db.py`
  (respeta `DB_PATH` env var, consistente con el resto del proyecto)
- `run_classifier()` simplificado: usa `get_connection()` en vez de re-calcular path

### evaluate.py — Default --limit consistente
- `--limit` default cambiado de 10 a 30 (igual que run.py)

### Tests — Dashboard + pre-existing bugs
- 18 tests nuevos para server.py (todos los endpoints REST + HTML serve)
- `test_excluye_ofertas_ya_enviadas` en test_db_evaluations.py: hardcode `offer_id IN (1)` → lookup dinámico
- `test_run_evaluate_procesa_oferta_y_guarda_en_db` en test_evaluate_cassettes.py: hardcode `offer_id = 1` → JOIN por source_id
- `test_multiple_ofertas_procesadas_en_orden` en test_pipeline.py: hardcode `offer_id IN (1, 2)` → JOIN por source_id
- test_feedback.py: unused `mock_save` y unused `pytest` import eliminados

### Resultado final
- **221 tests passing** (203 originales + 18 nuevos), 0 regresiones
- ruff format: 35 files OK
- ruff check: solo errores pre-existentes E402 (migrate.py, server.py)

### Bloqueadores
- Ninguno

---

## Evaluación de la codebase

### Observaciones recibidas y verificación contra código real

El 2026-06-11 se realizó una revisión externa del código. Verificación punto por punto:

| # | Observación | Veredicto | Evidencia |
|---|-------------|-----------|-----------|
| 1 | `[data-testid='sincedate-tag']` vs `[class*='published']` en scraper | ✅ **Parcial** — Ambos selectores existen en `_extract_published_at()`. `[data-testid='sincedate-tag']` es el primero (l.501). `[class*='published']` es fallback (l.503). No hay error. |
| 2 | Parseo "Hace 4h" no existe | ❌ **Incorrecto** — Sí existe en l.517: `re.search(r"hace\s+(\d+)\s*h", text)` |
| 3 | `timedelta` import dentro del método | ❌ **Incorrecto** — Está en `from datetime import datetime, timedelta, timezone` a nivel módulo (l.9) |
| 4 | `employer_id` siempre NULL | ✅ **Correcto** — `SearchStub` y `RawOfferDetail` no exponen `employer_id`. La función `_extract_employer_id()` en `fetch.py` solo se usaba en era Apify. |
| 5 | `parse_skills_required()` no valida JSON malformado | ❌ **Incorrecto** — Sí captura `JSONDecodeError` y `ValueError` y devuelve estructura vacía (l.136-137) |
| 6 | `description_clean` truncado a 8000 antes del LLM | ❌ **Incorrecto** — El scraper da datos estructurados. `extract_fields_with_llm()` ya no se llama en el pipeline (ADR-017). En prompts de evaluate los truncados son 1200 y 1800 caracteres. |
| 7 | `perfil[:2500]` y `perfil[:2000]` truncado posicional | ✅ **Correcto** — Evaluate l.464 y l.514. Truncado por posición, no semántico. |
| 8 | `relevance_flag` sin fallback determinista | ⚠️ **Tiene fallback** — `GAP_TO_FLAG.get(result["gap_type"], "stretch")` devuelve `"stretch"` si `gap_type` no está en el dict (l.326). Correcto pero silencioso. |
| 9 | Gap multiplier calculado pero no usado en score | ⚠️ **Por diseño** — ADR-013 documenta que gap es contexto cualitativo para HR LLM, no penalización numérica. |
| 10 | `location_match` persistido pero sin ponderar | ✅ **Correcto** — `location_match` es columna independiente en DB. La fórmula S = W_CORE·M_core + W_SEC·M_sec + W_EXP·F_exp + W_FIT·F_fit no lo incluye. `F_fit` (context_fit del LLM) recoge ubicación cualitativamente. |
| 11 | Tres parseos independientes de PERFIL.md por oferta | ❌ **Incorrecto** — Se hace una vez antes del `for` (evaluate.py:740-743), no por oferta. |
| 12 | `skills_hard_match` alias ambiguo de M_core | ✅ **Correcto** — La columna DB `skills_hard_match` almacena `round(M_core * 100)` (l.576). Nombre confuso. |
| 13 | `limit` compartido entre enrich y evaluate | ✅ **Correcto** — `run_fetch_company(limit=limit)` y `run_evaluate(limit=limit)` usan el mismo parámetro (run.py:166, 182) |
| 14 | `_run_start_time` global mutable | ✅ **Correcto** — `_run_start_time: float | None = None` variable global (run.py:204) |
| 15 | CV check en no-TTY sin log explícito de abort | ✅ **Correcto** — l.113-118: loggea warning con comando pero no un "Pipeline abortado" visible |
| 16 | Sin retry en ollama_call | ❌ **Incorrecto** — `ollama_call()` usa tenacity `@retry(stop=stop_after_attempt(3))` (l.102-106) |
| 17 | Sin métricas de calidad LLM | ✅ **Correcto** — No se registran contadores de JSON inválido, campos null o fuera de enum |
| 18 | PERFIL.md parseado con regex frágiles en múltiples sitios | ✅ **Correcto** — `load_skills_from_perfil`, `load_gap_from_perfil`, `load_experience_years_from_perfil` usan regex independientes |

### Resumen: 10 correctas, 6 incorrectas, 2 por diseño

---

## Plan de correcciones priorizado

### 🟢 Fáciles (código claro, bajo riesgo)

| # | Archivo | Fix | Líneas |
|---|---------|-----|--------|
| 1 | `infojobs_scraper.py` | Extraer `employer_id` desde HTML del detalle (link empresa con `em-i{HASH}`) — nuevo campo en `RawOfferDetail`, parser en `_parse_header_details` o nuevo método | `RawOfferDetail`, `parse_detail_html` |
| 2 | `fetch.py` | Guardar `employer_id` en `_upsert_offer_from_scraper()` usando nuevo campo de `RawOfferDetail` | `_upsert_offer_from_scraper` |
| 3 | `run.py` | Separar `--limit` en `--limit-eval` y `--limit-enrich` con defaults independientes | l.62, 166, 182 |
| 4 | `run.py` | Eliminar global `_run_start_time`, usar `t0 = time.monotonic()` local | l.204-209 |
| 5 | `run.py` | Añadir log `"[CV] Pipeline abortado — CV nuevo sin PERFIL.md actualizado"` en no-TTY | l.113-118 |
| 6 | `evaluate.py` | Documentar que `skills_hard_match` = M_core (o renombrar a `m_core`) | l.576, _COLUMNS, schema.sql |

### 🟡 Medios (refactor localizado)

| # | Archivo | Fix | Detalle |
|---|---------|------|---------|
| 7 | `evaluate.py` | Cambiar `perfil[:2500]` y `perfil[:2000]` en prompts HR/final → extraer secciones específicas por regex | l.464, 514 |
| 8 | `role_classifier.py` | Cambiar `description[:2000]` → extraer secciones relevantes | l.237 |
| 9 | `evaluate.py` | Unificar parseo de PERFIL.md en un objeto `CandidateProfile` (skills, gap, years, city, concerns) — una sola llamada al inicio | l.740-743 |
| 10 | `role_classifier.py` | Añadir warning cuando `relevance_flag` cae al default `"stretch"` sin gap_type conocido | l.326 |

### 🔴 Estratégicos (requieren ADR o discusión)

| # | Impacto | Propuesta |
|---|---------|-----------|
| 11 | Medio | `location_match` sin ponderación en score — abrir ADR para decidir si añadir `W_LOC * location_match` o mantener status quo (F_fit ya recoge ubicación cualitativamente) |
| 12 | Medio | Métricas de calidad LLM — añadir contadores en `ollama_call()`: `json_retries`, `invalid_json_count`, `null_field_count`. Persistir en tabla `llm_metrics` o log estructurado. |
| 13 | Bajo | `CandidateProfile` compartido entre evaluate.py y role_classifier.py — refactorizar para evitar parseo duplicado de PERFIL.md |

### Ya está bien (no corregir)

- Gap multiplier no usado → ADR-013, decisión consciente
- `ollama_call` sin retry → tiene (tenacity 3 intentos)
- Parseo horas → existe
- `timedelta` import → está al tope del módulo
- `description_clean` truncado → no se pasa al LLM
- Parseos independientes de PERFIL → se hacen una vez

### Total: 13 cambios (6 🟢, 4 🟡, 3 🔴)

### Próximos pasos (ampliados)
- 🟢 Ejecutar fixes fáciles (#1-6)
- 🟡 Ejecutar fixes medios (#7-10)
- 🔴 Discutir estratégicos y crear ADR si aplica (#11-13)
- T-5h Fase 2 (branding + microcopy dashboard)
- Fase 4 (role_discovery, market_signals, strategic_advisor)
