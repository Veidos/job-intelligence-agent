# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-17
**Fase activa:** Pipeline Run dashboard + análisis de datos

## Logros de la sesión

### 1. Date scope + fallback histórico (send.py)
- `get_top_offers(date_scope='latest')` filtra por `MAX(date(fetched_at))`
- `send_daily()`: intenta últimas ofertas; si no hay, cae a backlog histórico con header y fecha visibles
- 3 tests nuevos, 225 total

### 2. Pipeline Run dashboard (nueva pestaña)
Nuevo botón **Pipeline** en el nav del dashboard con:

- **Selector de ejecución**: dropdown con todas las fechas de run, default al último
- **Funnel horizontal**: Fetch → Clasif. → Eval. → ≥35 → ≥50 → Enviadas, cada paso con número + % acumulado
- **Componentes por banda**: barras agrupadas <30 / 30–49 / 50+ con M_core, F_exp, Ubic., Mercado — valores numéricos sobre cada barra
- **Compatibilidad con el entorno (F_fit)**: stacked bar con tooltip de % por categoría alta/media/baja
- **Tabla de accionables**: ofertas score ≥ 50 sin apply_block, con enlace a detalle

### 3. Análisis de scoring (hallazgos)
- **Cuello de botella: M_core** — skills_hard_match pasa de 7.5 (<30) a 75.5 (50+), es el factor que realmente discrimina
- **F_fit no discrimina** — environment_compatibility es plana entre bandas de score
- **Ubicación penaliza parejo** — location_match plano (38-43) sin correlación con score

## Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `src/dashboard/server.py` | + endpoint `GET /api/pipeline-runs` (stats agrupadas por fecha) |
| `src/dashboard/templates/dashboard.html` | + nav link "Pipeline" + section con funnel/charts/tabla |
| `src/dashboard/static/app.js` | + `loadPipelineRuns()` + `renderPipelineRun()` + sub-renderers |
| `src/dashboard/static/style.css` | + estilos `.pipeline-run-select`, `.funnel-row`, `.funnel-step` |

## Tests
- **225 tests passing** (sin cambios en tests — funcionalidad nueva)
- **Ruff:** 0 errores nuevos

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080 (incluye pestaña Pipeline)
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
