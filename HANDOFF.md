# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-08-26
**Fase activa:** Pipeline completo E2E validado — Grammar constraints + Run exitoso

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
