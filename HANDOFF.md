# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-30
**Fase activa:** Decoy detection + limpieza DB

## Logros de la sesión

### Commits (6)

| # | Commit | Cambio |
|---|--------|--------|
| 1 | `ceb2d7f` | Anti-bot hardening base: sleep log-normal, fingerprints rotatorios, lockfile 20h, referer real, MAX_DETAILS_PER_SESSION=8 |
| 2 | `d6addb1` | Dedup intra-run en fetch.py (seen_ids set) |
| 3 | `97f6ea9` | Fix city vacío: fallback a URL slug |
| 4 | `e508c40` | Endpoint /api/scraper/cooldown + countdown en dashboard |
| 5 | `9fbbcbb` | Docs: HANDOFF, PLANS, MEMORIES, ADR-022 |
| 6 | `COMMIT` | Fix MAX_DETAILS global (no per-keyword) + decoy detection `_is_decoy_page()` + limpieza DB |

### Archivos modificados (7)

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

⚠️ **Search funciona, Details devuelven decoy.** El anti-bot hardening (ADR-022) evitó 403 pero Distil Network sirve "No podemos identificar tu navegador" como 200 OK en detail pages. Se añadió `_is_decoy_page()` para detectar y saltar estas ofertas automáticamente.

### Tenencias

- **IP marcada para detail pages.** Search funciona, pero cualquier detail request devuelve decoy content.
- **10 ofertas basura eliminadas** de la DB.
- **`_is_decoy_page()`** protege contra futuras contaminaciones.
- **ADR-022 documenta:** si IP queda bloqueada en details, proxy residencial es la única salida.

### Próximo paso

Decidir entre:
1. **Proxy residencial rotatorio** — implementar transporte HTTP con proxies (nuevo ADR)
2. **Esperar días/semanas** a que la IP se enfríe sola (riesgo: Distil no olvida)
3. **Volver a Apify** como fallback mientras tanto

### Comandos

```bash
python src/dashboard/server.py                # Dashboard en :8080
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
