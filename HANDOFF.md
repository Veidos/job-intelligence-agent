# HANDOFF.md — Estado de sesión

**Última actualización:** 2026-08-25
**Fase activa:** Pipeline desbloqueado — Scrapling + capa bronze (ADR-023)

## Logros de la sesión

### Resumen
Sesión de reactivación tras 8 semanas de pausa. Se evaluó Scrapling (D4Vinci)
como transporte alternativo vía PoC empírico, se descubrió que el bloqueo Distil
expiró, y se migró el transporte por capas añadiendo una capa bronze pura.

### PoC Scrapling (7 requests totales, cero escrituras DB)

| Test | Resultado |
|------|-----------|
| T1 Search HTTP | ✅ 200 OK, 10 tarjetas, 0 decoy |
| T2 Details warmed HTTP | ✅ 2/2 contenido real (desc 2.4K/3.8K chars) |
| T3 Details stealth | ✅ 2/2 contenido real |

Hallazgos: IP fría (Distil expira ~8 semanas) · warming funciona por HTTP puro ·
Scrapling 0.4.15 compatible py3.14 · InfoJobs cambió su DOM
(`.ij-OfferDetailDescription` muerto; parser de producción sobrevive por cadena
de fallbacks). Resultados completos en `scraper_lab/scrapling_poc/results/`.

### Migración por capas (4 commits + docs)

| # | Commit | Cambio |
|---|--------|--------|
| 1 | `2873ec7` | PoC completo con snapshots .gz y RESULTS.md |
| 2 | `69d5847` | Capa bronze `scraper_raw_html` (HTML gzip+SHA-256 ANTES de parsear) |
| 3 | `ae7259c` | ScraplingTransport: warming + escalada stealth automática + factoría SCRAPER_BACKEND |
| 4 | `ff9e186` | Selector muerto eliminado + tests frescura DOM real |
| 5 | (este)   | Docs: ADR-023 + triada |

### Verificación

- **265 tests passing** (231 previos + 21 bronze/transporte + 13 frescura)
- **Ruff:** ✅ 0 errores en src/
- Migración aplicada a jobs.db real (tabla aditiva, sin tocar existentes)

### Decisiones clave (ADR-023)

- `SCRAPER_BACKEND=scrapling` (rollback instantáneo: `curl_cffi`)
- `SCRAPER_STEALTH_FALLBACK=1`: ante 2 decoys → browser solo en details;
  8 fallos → abort limpio sin reintentos
- Capa bronze SIN TTL (~350MB/año): incluye search pages para market_signals
- NO persistir cookies Distil (<1h vida); warm fresco cada run (+1 request)

### Próximos pasos

1. **Run real del pipeline** (`python src/pipeline/run.py --skip-cv-check`) para
   validar E2E con datos frescos y confirmar Telegram
2. **Configurar cron diario** (`setup_cron.sh`) — automatización pendiente desde siempre
3. Webshare/proxies: crear cuenta solo si Distil reaparece pese a todo
   (vía ISP static $0.30/proxy; integración nativa vía `proxy=` de Scrapling)
4. Fase 4: `market_signals.py` consumirá los search snapshots de scraper_raw_html

### Comandos

```bash
python src/dashboard/server.py                # Dashboard en :8080
ruff check src/ && ruff format src/ --check   # Lint
pytest tests/ -q                              # Tests (265)
python src/pipeline/fetch.py --dry-run        # Fetch sin efectos laterales
```
