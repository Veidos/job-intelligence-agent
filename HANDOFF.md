# HANDOFF.md — Estado de sesión (actualizar al cerrar)

**Última actualización:** 2026-06-11
**Fase activa:** Sesión de calidad — 11 fixes implementados, ADR-018 creado.

## Cambios de la sesión actual (2026-06-11)

### 🟢 Fix #1-2 — employer_id desde scraper
- `RawOfferDetail.employer_id` añadido al dataclass + `_extract_employer_id()` desde `em-i{HASH}` en company link
- `_upsert_offer_from_scraper()` ahora persiste `employer_id` en INSERT y UPDATE (COALESCE)
- `fetch_company.py` ya usaba `employer_id` como `infojobs_company_id` — sin conflictos

### 🟢 Fix #3-5 — run.py
- `--limit` separado en `--limit-eval` (default 30) y `--limit-enrich` (default 50)
- Global `_run_start_time` eliminada, `t0 = time.monotonic()` local
- Log `"[CV] Pipeline abortado — CV nuevo sin PERFIL.md actualizado"` en no-TTY

### 🟢 Fix #6 — skills_hard_match documentado
- No renombrado (25 referencias en schema, server, tests, fixtures)
- Comentario explicativo en `_COLUMNS`: `# skills_hard_match (columna DB) = round(M_core * 100)`

### 🟡 Fix #7 + #9 — CandidateProfile + excerpt()
- `src/utils/candidate_profile.py` — nuevo módulo con `CandidateProfile.from_perfil()`
- Parseo unificado de PERFIL.md en 1 pass con regex por sección (`re.DOTALL | re.IGNORECASE`, lookahead `(?=\n##|\Z)`)
- `perfil_sections: dict[str, str]` preserva cada sección completa
- `excerpt(nombres_seccion)` compone texto para prompts sin truncado posicional
- `perfil[:2500]` y `perfil[:2000]` reemplazados por `profile.excerpt()`
- `personal_concerns` garantizado en HR LLM
- `raw_perfil` preservado con `# TODO: eliminar` para migración gradual

### 🟡 Fix #8 — Prioridad inversa en descripción
- `_extract_relevant_description()` en classifier: bloque requisitos (hasta 1000 chars) + intro (resto hasta 2000)
- Marcadores: "requisitos", "se requiere", "formación", "estudios mínimos", etc.

### 🟡 Fix #10 — Warnings en fallbacks silenciosos
- `GAP_TO_FLAG.get(gap_type, "stretch")` ahora loggea warning si gap_type no está en dict
- `relevance_corrected` validado contra `{"core", "adjacent", "stretch", "temporal", None}`, warning si fuera

### #12 — LLM quality metrics
- 3 contadores en `ollama_client.py`: `calls`, `json_parse_failures`, `empty_responses`
- `get_llm_metrics()` loggeado al final del pipeline en `run.py`
- In-memory, no persistidos en DB
- `null_fields` no implementado (responsabilidad del caller)

### #11 + #13 — Cerrados
- **#11:** `location_match` status quo — no se pondera en score. ADR-018 documenta.
- **#13:** `CandidateProfile` compartido — resuelto por #9 en `src/utils/`

### Resultado final
- **221 tests passing**, 0 regresiones
- 10 cambios implementados + 2 cerrados
- ADR-018 creado: CandidateProfile, LLM Metrics, location_match Status Quo
- ruff: solo 3 pre-existing E402 (server.py, migrate.py)

### Bloqueadores
- Ninguno
