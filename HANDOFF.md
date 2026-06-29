# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-29
**Fase activa:** Anti-bot hardening del scraper (sleep log-normal, fingerprints rotatorios, lockfile 20h, referer real, límite 8 details/sesión)

## Logros de la sesión — Anti-bot hardening

### Cambios en el scraper (2 archivos)

| # | Cambio | Archivo |
|---|--------|---------|
| 1 | `_FINGERPRINTS` reducido a solo Chromium: chrome131/124/120/119, edge101 | `infojobs_scraper.py` |
| 2 | `_rate_limit()` reemplazado por `lognormvariate(mu=2.5, sigma=0.6)` clamp [8, 45]s | `infojobs_scraper.py` |
| 3 | `_fetch()` acepta `headers: dict \| None = None` | `infojobs_scraper.py` |
| 4 | `detail()` acepta `search_url`, pasa Referer + Sec-Fetch-{Site,Mode} | `infojobs_scraper.py` |
| 5 | `self.jitter` eliminado (código muerto) | `infojobs_scraper.py` |
| 6 | Lockfile 20h entre runs (protegido vs corrupto) | `fetch.py` |
| 7 | `MAX_DETAILS_PER_SESSION = 8` + slicing en detail loop | `fetch.py` |
| 8 | `search_url` real construido desde keyword para Referer | `fetch.py` |

### Tests
- **231 tests passing** (0 regresiones)
- **Ruff:** ✅ **0 errores**
- Sin cambios en tests (usan `InfoJobsParser`, no `InfoJobsScraper`)

## Próximo paso
Probar paso 2 del plan: `python -c "from src.pipeline.infojobs_scraper import InfoJobsScraper; s = InfoJobsScraper(); print(s.search('data analyst', pages=1))"`
Si devuelve stubs → esperar 24h y ejecutar run completo.
Si da 403 → la IP está quemada para InfoJobs.

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
