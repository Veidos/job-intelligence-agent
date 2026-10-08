# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-10-08
**Fase activa:** Baseline `2dce06a`; próxima revisión: parsing JS de fechas con zona horaria

## Rollback de código — 2026-10-07

- Revertidos en `main` los cinco commits del 2026-10-05; el código de aplicación vuelve al estado de `2dce06a`.
- Verificación sobre el estado restaurado: 274 tests pasan en Python 3.11 y 3.14; Ruff limpio.
- La base `data/jobs.db` no se restauró. Se conservaron los registros raw/bronze y el run histórico; las ofertas del run 42 se limpiaron por petición.
- `data/jobs.db.v1` es del 2026-06-11; no usar como restauración porque perdería datos posteriores.
- Run 40 (2026-09-01) funcionó con el scraper anterior; run 41 (2026-10-05), antes del último cambio del scraper, obtuvo 0 raws por los muros nuevos de InfoJobs. Revertir código no revierte el cambio externo del sitio.
- No se hicieron peticiones a InfoJobs durante el rollback. No lanzar otro run hasta decidir cómo tratar la protección actual y los registros falsos de la DB.
- Sonda controlada posterior al rollback: 1 búsqueda + 2 fichas HTTP (3 peticiones, callback solo en memoria, sin DB ni Telegram). 3/3 respuestas reales, sin captcha; fichas completas (3.216 y 2.536 chars de descripción). Una coincidió con «Data Analyst»; la otra fue «Agente Inmobiliario - Cantabria», fuera de tema. Esto confirma conectividad puntual, no fiabilidad de una ejecución larga ni precisión de búsqueda.
- Por petición del usuario, se eliminaron las 26 ofertas del run 42 (IDs 311–336), sus 26 evaluaciones y el rol falso `screening_test_administrator`. Se conservaron 26 scraper raws, 52 bronze rows y `search_runs.id=42`; copia previa íntegra en `data/jobs.db.pre-run42-cleanup-20261008.sqlite`. ADR-025 documenta causa, fallo de revisión y limpieza.
- También se eliminó manualmente la oferta id 49 (`Junior engineer - Sales Department`) y su evaluación: `published_at=2026-06-11T17:04:31.238881+00:00` se convertía en `Invalid Date` en `app.js`, por lo que el filtro >30 días no la ocultaba. Se conservó su raw; copia previa en `data/jobs.db.pre-offer49-delete-20261008.sqlite`.
- Estado DB tras ambas limpiezas: 317 ofertas; `integrity_check=ok`, 0 referencias FK rotas. La búsqueda temporal del dashboard aún requiere corregir `_parseDate` para sufijos de zona horaria.

## Logros de la sesión

### Resumen
Sesión de reactivación tras 8 semanas de pausa. Se completaron 3 fases:
1. Scrapling transport + bronze layer (ADR-023)
2. Grammar constraints JSON vía Ollama format (ADR-024)
3. Run E2E completo con resultados reales

### PoC Scrapling (7 requests totales, cero escrituras DB)

| Test | Resultado |
|------|-----------|
| T1 Search HTTP | ✅ 200 OK, 10 tarjetas, 0 decoy |
| T2 Details warmed HTTP | ✅ 2/2 contenido real (desc 2.4K/3.8K chars) |
| T3 Details stealth | ✅ 2/2 contenido real |

### Migración por capas (5 commits)

| # | Commit | Cambio |
|---|--------|--------|
| 1 | `2873ec7` | PoC completo con snapshots .gz y RESULTS.md |
| 2 | `69d5847` | Capa bronze `scraper_raw_html` (HTML gzip+SHA-256 ANTES de parsear) |
| 3 | `ae7259c` | ScraplingTransport: warming + escalada stealth automática + factoría SCRAPER_BACKEND |
| 4 | `ff9e186` | Selector muerto eliminado + tests frescura DOM real |
| 5 | `764a063` | Docs: ADR-023 + triada |
| 6 | `6ec33b3` | Grammar constraints JSON vía Ollama format (ADR-024) |

### Run E2E #34 — Resultados reales

| Métrica | Valor |
|---------|-------|
| Ofertas fetcheadas | 8 (limitadas por MAX_DETAILS_PER_SESSION=8) |
| Clasificadas | 8/8 |
| Empresas enriquecidas | 2 |
| Evaluadas | 7/8 (1 timeout gemma4) |
| JSON parse failures | **0** ✓ |
| Enviadas a Telegram | 3 |
| Duración total | 38 min |
| LLM calls totales | 43 |

### Verificación post-run

- **274 tests passing** (231 previos + 21 bronze/transporte + 13 frescura + 9 schemas)
- **Ruff:** ✅ 0 errores en src/
- **Bronze layer:** 14 rows (6 search + 8 detail), ~1.3 MB comprimido
- **Telegram:** ✅ Mensaje enviado con 3 ofertas
- **GPU:** ✅ gemma4:e4b + qwen2.5:7b offloaded a GPU
- **ScraplingTransport:** ✅ Activo (factory→ScraplingTransport, chrome131)

### Decisiones clave

- **ADR-023:** Scrapling transport + bronze layer (rollback a curl_cffi si es necesario)
- **ADR-024:** Grammar constraints vía Ollama `format` con JSON Schema estricto
  - `think=true` + `format` silencia traza think (comportamiento pre-existente)
  - Razonamiento exigible vive en campos `required` del schema
  - 0 JSON parse failures en run real

### Problemas identificados

1. **MAX_DETAILS_PER_SESSION = 8** — cap demasiado conservador, solo procesa 2 de 6 keywords
2. **limit_eval = 30** — por defecto evalúa solo 30 ofertas/run (ok para cron diario)
3. **Timeout gemma4** — 1 oferta (Alcorce) timeout a 180s, quedó sin evaluar
4. **Lockfile 20h** — cooldown entre runs, bloquea runs inmediatos de prueba

### Próximos pasos

1. **Eliminar MAX_DETAILS_PER_SESSION** — sin cap en fetch (commit pendiente)
2. **Run de prueba con limit_eval=0** — evaluar todas las ofertas de 7 días
3. **Configurar cron diario** (`setup_cron.sh`) — automatización pendiente
4. Webshare/proxies: crear cuenta solo si Distil reaparece
5. Fase 4: `market_signals.py` consumirá search snapshots de scraper_raw_html

### Comandos

```bash
python src/dashboard/server.py                # Dashboard en :8080
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests (274)
python src/pipeline/run.py --skip-cv-check    # Pipeline completo
curl -X POST http://localhost:8080/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"since_date":"_7_DAYS","limit_eval":0}'  # Run sin límites
```
