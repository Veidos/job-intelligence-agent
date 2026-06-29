# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-29
**Fase activa:** Anti-bot hardening + countdown dashboard

## Logros de la sesión

### Commits (4)

| # | Commit | Cambio |
|---|--------|--------|
| 1 | `ceb2d7f` | Anti-bot hardening base: sleep log-normal, fingerprints rotatorios, lockfile 20h, referer real, MAX_DETAILS_PER_SESSION=8 |
| 2 | `d6addb1` | Dedup intra-run en fetch.py (seen_ids set) |
| 3 | `97f6ea9` | Fix city vacío: fallback a URL slug |
| 4 | `e508c40` | Endpoint /api/scraper/cooldown + countdown en dashboard |

### Archivos modificados (6)

| Archivo | Cambios |
|---------|---------|
| `src/pipeline/infojobs_scraper.py` | Fingerprints, _rate_limit log-normal, headers en _fetch/detail, jitter eliminado |
| `src/pipeline/fetch.py` | Lockfile 20h, MAX_DETAILS_PER_SESSION=8, seen_ids dedup, search_url para Referer |
| `src/dashboard/server.py` | import time + endpoint /api/scraper/cooldown |
| `src/dashboard/static/app.js` | loadScraperCooldown() + setInterval en init |
| `src/dashboard/templates/dashboard.html` | span #scraperCooldownDisplay |
| `docs/adr/ADR-022-anti-bot-hardening.md` | Nuevo ADR documentando la sesión |

### Tests

- **231 tests passing** (0 regresiones)
- **Ruff:** ✅ **0 errores**
- Sin cambios en tests

### Verificación IP

✅ Search test: `s.search(query='data analyst', page_limit=1, max_items=5)` → 5 stubs con datos reales, 0 errores. IP limpia.

### Próximo paso

Ejecutar run completo cuando venza lockfile (~20h tras último fetch real):
```bash
python src/pipeline/fetch.py --max-items 30 --since-date _7_DAYS
```

### Comandos

```bash
python src/dashboard/server.py                # Dashboard en :8080
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
