# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-06-18
**Fase activa:** Sesión de calidad — 13 ítems del análisis intensivo

## Logros de la sesión

### 13 ítems del análisis intensivo implementados

| # | Ítem | Archivo | Cambio |
|---|------|---------|--------|
| 1 | Console handler duplicado | `run.py` | `StreamHandler` movido dentro de `setup_logging()` con guardia |
| 2 | think log → DEBUG | `ollama_client.py` | `log.info` → `log.debug` |
| 3 | Autenticación Telegram | `bot.py`, `.env.example` | Decorador `@require_auth` usando `TELEGRAM_USER_ID` |
| 4 | sys.path en bot.py | `bot.py` | Eliminado (paquete instalado vía `pip install -e .`) |
| 5 | offers_fetched incorrecto | `fetch.py`, `run.py` | `run_fetch_scraper()` retorna `{"new": ..., "total": ...}` |
| 6 | Conexiones sin try/finally | `models.py`, `handlers.py`, `send.py` | 4 funciones envueltas en `try/finally` |
| 7 | Commit por fila | `fetch.py` | `conn.commit()` por iteración en scraper raw |
| 8 | Truncado JSON seguro | `fetch.py` | Truncar `description` antes de serializar |
| 9 | Acentos en ciudades | `evaluate.py` | `unicodedata.normalize('NFD', ...)` |
| 10 | role_level/role_level_label zombies | `migrate.py`, `schema.sql` | `drop_offers_zombie_columns()` nueva |
| 11 | apify_raw_responses legacy | `schema.sql` | Comentario legacy |
| 12 | active_role_level reserved | `schema.sql` | Comentario reserved for future |
| 13 | Métricas con Lock | `ollama_client.py` | `threading.Lock` + `_inc_metric()` |

### Documentación
- `docs/SETUP.md`: añadido `pip install -e .`
- `README.md`: añadido `pip install -e .`, eliminado `pip install flask` redundante
- `.env.example`: añadido `TELEGRAM_USER_ID`

## Tests
- **231 tests passing** (0 regresiones)
- **Ruff:** 0 errores nuevos (8 pre-existentes: E402 en server/migrate/backfill, W291 en cv_extractor/role_classifier)

## Comandos
```bash
python src/dashboard/server.py                # Dashboard en :8080
python src/pipeline/run.py                    # Pipeline completo
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests
```
