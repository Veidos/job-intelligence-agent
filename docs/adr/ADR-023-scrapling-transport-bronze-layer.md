# ADR-023: Transporte Scrapling + capa bronze pura

**Estado:** Active
**Fecha:** 2026-08-25
**Contexto:** ADR-016 (scraper propio), ADR-022 (anti-bot hardening)
**Evidencia:** `scraper_lab/scrapling_poc/results/RESULTS.md` (PoC T1-T3 PASS)

## Problema

Dos problemas convergentes tras 8 semanas de pipeline parado:

1. **Blocker Distil (desde jun-2026):** detail pages devolvían decoy content
   (HTTP 200 con "No podemos identificar tu navegador"). ADR-022 dejó tres
   salidas abiertas: proxy residencial, esperar enfriamiento de IP, o Apify.
2. **Capa raw impura:** `scraper_raw_responses.payload` almacena el dict ya
   parseado (`RawOfferDetail`), no el HTML original. El HTML se descartaba en
   memoria. Este proyecto pagó esa deuda dos veces: 21 ofertas re-scrapeadas
   por descripciones vacías y un backfill de `published_at` complejo (1 oferta
   perdida) porque no quedaba fuente primaria que re-parsear.

## Evidencia del PoC (2026-08-25, 7 requests totales)

| Test | Transporte | Resultado |
|------|-----------|-----------|
| T1 Search | Scrapling FetcherSession HTTP | ✅ 200 OK, 10 tarjetas, 0 decoy |
| T2 Details warmed | Misma sesión: warm→dwell→details+Referer | ✅ 2/2 contenido real |
| T3 Details stealth | StealthySession (patchright headless) | ✅ 2/2 contenido real |

Conclusiones:
1. **La IP estaba fría** — el bloqueo Distil expira (~8 semanas). La constraint
   era reputación de IP, no fingerprinting.
2. **El patrón warming funciona por HTTP puro** — el browser solo es escalada.
3. Scrapling 0.4.15 compatible con Python 3.14; sesiones con cookie jar;
   parser CSS propio funcional.
4. InfoJobs cambió su DOM: `.ij-OfferDetailDescription` desapareció (el
   selector primario `mainContent` sigue vivo; producción sobrevivió de milagro
   por la cadena de fallbacks).

## Decisión

### 1. Scrapling como transporte principal

`src/pipeline/scrapling_transport.py`:

- `FetcherSession(impersonate=chrome131)` con cookie jar persistente.
- Patrón warming: la primera búsqueda gana cookies Distil; los details llevan
  `Referer` + `Sec-Fetch-*` de la búsqueda que los generó.
- Delays log-normal clamp [8,45]s heredados de ADR-022.
- Todo el parseo sigue en `InfoJobsParser` (fuente única). El transporte solo
  mueve bytes.

### 2. Circuito anti-bloqueo con umbrales definidos

```
detail() → decoy? ──sí──► consecutive_decoys++
             │                    │ ≥ 2 → escalar a StealthySession
             no                   │ ≥ 8 fallos totales → ScraperBlockedError
             ▼                          (sin tormentas de reintentos)
     parse normal, reset contador
```

- Solo los DETAILS van por browser stealth (~30s/unidad); las búsquedas siguen
  en HTTP barato siempre.
- `SCRAPER_STEALTH_FALLBACK=1|0` en `.env`. Requiere `scrapling install`
  (Chromium ~300MB); sin él, fallback desactivado en runtime.

### 3. Capa bronze pura: `scraper_raw_html`

```sql
CREATE TABLE IF NOT EXISTS scraper_raw_html (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('search','detail')),
    offer_id TEXT, url TEXT NOT NULL, http_status INTEGER,
    html_gz BLOB NOT NULL,          -- HTML ORIGINAL gzip nivel 9 (~88% ratio)
    content_hash TEXT NOT NULL,     -- SHA-256 del HTML sin comprimir
    created_at DATETIME DEFAULT (datetime('now'))
);
```

- Cada respuesta se archiva ANTES de parsearse (hook `on_raw_html`).
- Incluye páginas de búsqueda (materia prima futura para market_signals).
- Append-only e inmutable. Retención: sin TTL (~350 MB/año comprimido).
- Tabla ADITIVA: `scraper_raw_responses` intacta (transición dual); su
  limpieza será otro ADR.

### 4. Rollback instantáneo

`SCRAPER_BACKEND=curl_cffi` revierte al scraper legacy sin tocar código.
`InfoJobsScraper` queda 100% sin modificar (tradeoff documentado: el modo
rollback no archiva bronze).

## Alternativas rechazadas

| Alternativa | Razón |
|-------------|-------|
| Webshare free (10 datacenter proxies) | ASN datacenter compartido = pre-filtrado por Distil; geo US/DE sospechoso para infojobs.net. Aparcado hasta necesidad real; si llega bloqueo, ISP static ($0.30/proxy) es la vía |
| Volver a Apify | Coste €/run, campos estructurados peores (ADR-016 documentó sus límites), dependencia externa |
| ALTER scraper_raw_responses | Cambio de UNIQUE exige rebuild de tabla en SQLite; riesgo innecesario con tabla viva leyéndose en producción |
| Persistir cookies entre runs | Las cookies Distil son de sesión (<1h); con lockfile de 20h enviaríamos cookies caducadas — peor señal que warm fresco (+1 request/run) |

## Consecuencias

- **Positivas:** Pipeline desbloqueado sin coste mensual. Fuente primaria
  inmutable permite re-parsear histórico ante cambios de DOM/parser (tests de
  frescura lo detectan antes de producir). Escalada stealth automática cubre
  reaparición parcial del bloqueo.
- **Negativas:** Dependencia nueva (scrapling[fetchers], pin >=0.4.15,<0.5).
  Run algo más largo por delays warming. Bronze crece ~1MB/día comprimido.
- **Futuro:** Si Distil vuelve a bloquear pese a warming+stealth → proxy
  residencial/ISP rotatorio vía `proxy=` nativo de Scrapling (nuevo ADR con
  presupuesto). Limpieza futura de `payload` dual y legacy Apify.
