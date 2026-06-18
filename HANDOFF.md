# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-17
**Fase activa:** Dashboard UI fixes + Backfill + Post-merge validación

## Logros de la sesión

### Fix 3 — Post-merge scraper core (ADR-021)
- `_merge_scraper_skills_into_llm()` implementada en `fetch.py`
- Skills del `<dl>` de InfoJobs son siempre core — el LLM no puede moverlas
  a secondary ni omitirlas. Normalización `re.sub(r"[\s\-_./]", ...)` match robusto.
- 6 tests unitarios en `test_fetch_merge_skills.py`

### Pipeline run real (23 ofertas nuevas)
- Fetch: 32 raws, 23 nuevas ofertas. Classify + Evaluate: 23 evaluadas, 0 errores.
- **Check 1:** 23/23 ofertas con secondary poblado ✅
- **Check 2:** `secondary_redistributed: false` en todas (W_SEC=0.15 activo). M_sec > 0 en 8 ofertas ✅
- **Check 3:** 0 skills del `<dl>` fugaron a secondary (post-merge verificado) ✅
- 120 LLM calls, 0 fallos JSON. 3 ofertas enviadas a Telegram.
- **Verificación adicional:** Skills del `<dl>` vacío (ej. "AI Engineer") no son protegibles
  por post-merge — la clasificación LLM puede poner skills core en secondary. Es calidad de prompt.

### Dashboard UI fixes
- **Runs table movida a Pipeline:** "Detalle de ejecuciones" (antes en Monitor colapsado)
  ahora en Pipeline como desplegable, junto con "Resumen por ejecución"
- **Doughnut tooltip con %:** tooltip de "Empresas por sector" ahora muestra
  "Tecnología: 12 (32.4%)" en vez del número crudo
- **Filtro renombrado:** "Mostrar bloqueadas" → "Ocultar bloqueadas", consistente
  con los otros dos filtros. Lógica invertida + `checked` por defecto

### Backfill completado (51 ofertas legacy)
- `src/pipeline/backfill_scores.py` actualizado: ahora actualiza weights aunque el
  score no cambie, si falta el flag `secondary_redistributed`
- 51 ofertas legacy pasaron de `redistributed: null` → `redistributed: true`
- Dataset homogéneo: 117 legacy (true) + 23 nuevas (false), sin grupos huérfanos

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `src/pipeline/fetch.py` | + `_merge_scraper_skills_into_llm()` + post-merge en `_upsert_offer_from_scraper` |
| `tests/unit/test_fetch_merge_skills.py` | + 6 tests (3 funcionales + 3 edge) |
| `docs/adr/ADR-021-post-merge-scraper-core.md` | Nueva ADR |
| `src/dashboard/templates/dashboard.html` | Runs table movida de Monitor a Pipeline; filter rename |
| `src/dashboard/static/app.js` | `loadRuns()` movida a Pipeline; doughnut % tooltip; filter invertido |
| `src/pipeline/backfill_scores.py` | Fix: actualiza weights aunque score no cambie si falta flag |
| `docs/DASHBOARD_STYLE.md` | + sección 8: convención de filtros |
| `HANDOFF.md` | Actualizado |
| `PLANS.md` | Actualizado |
| `MEMORIES.md` | + dashboard UI learnings |

## Tests
- **231 tests passing** (sin cambios en test count — dashboard UI son JS/HTML)
- **Ruff:** 0 errores nuevos (solo pre-existentes)

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
