# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-17
**Fase activa:** Fix 3 — Post-merge scraper core (ADR-021)

## Logros de la sesión

### Fix 3 — Post-merge scraper core (ADR-021)
- `_merge_scraper_skills_into_llm()` implementada en `fetch.py`
- Skills del `<dl>` de InfoJobs son siempre core — el LLM no puede moverlas
  a secondary ni omitirlas
- Normalización mínima `re.sub(r"[\s\-_./]", "", ...)` para match robusto
  entre variantes del scraper y LLM ("Power BI" vs "PowerBI")
- 6 tests unitarios en `test_fetch_merge_skills.py`
- ADR-021 documenta la decisión

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `src/pipeline/fetch.py` | + `_merge_scraper_skills_into_llm()` + post-merge en `_upsert_offer_from_scraper` |
| `tests/unit/test_fetch_merge_skills.py` | + 6 tests (3 funcionales + 3 edge) |
| `docs/adr/ADR-021-post-merge-scraper-core.md` | Nueva ADR |
| `HANDOFF.md` | Actualizado |
| `PLANS.md` | Actualizado |
| `MEMORIES.md` | + aprendizaje post-merge |
| `docs/PIPELINE.md` | Sección fetch actualizada con regla post-merge |

## Tests
- **231 tests passing** (225 + 6 nuevos en test_fetch_merge_skills.py)
- **Ruff:** 0 errores

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080 (incluye pestaña Pipeline)
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
