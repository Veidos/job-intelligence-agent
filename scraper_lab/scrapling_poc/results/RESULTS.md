# RESULTS.md — PoC Scrapling vs InfoJobs (2026-08-25)

> Experimento en `scraper_lab/scrapling_poc/`. Cero escrituras en DB.
> Contexto: detail pages bloqueadas por Distil desde 2026-06-30 (ADR-022).
> IP doméstica "fría" tras ~8 semanas sin tráfico.

## Matriz de resultados

| Test | Transporte | Requests | Resultado | Evidencia |
|------|-----------|----------|-----------|-----------|
| **T1 Search** | FetcherSession HTTP (`chrome131`) | 1 | ✅ PASS | 200 OK, 1.18 MB, 10 tarjetas, 0 decoy |
| **T2 Details HTTP warmed** | Misma sesión, warm→dwell→details con Referer | 3 | ✅ PASS | 2/2 páginas reales: desc 2.397 y 3.833 chars |
| **T3 Details Stealth** | StealthySession (patchright Chromium headless) | 3 | ✅ PASS | 2/2 páginas reales: mismos contenidos |

**Total: 7 requests** (5 previstos + 2 por warming independiente de cada proceso).
Delays log-normal 8–45s entre requests (patrón ADR-022).

## Hallazgos

### 1. La IP está fría — el bloqueo Distil expiró
T2 obtuvo detail pages **reales por HTTP puro** (sin browser). En jun-2026 las mismas
requests devolvían decoy de 200 OK. Conclusión: la constraint era reputación de IP,
no fingerprinting. El referer de Google que Scrapling añade por defecto no generó
problemas (T3 sirvió contenido real incluso con él).

### 2. El patrón warming funciona y es barato
Search primero → cookies de sesión → dwell log-normal → details con `Referer` de la
búsqueda. Es exactamente lo que recomiendan las guías de Distil/Imperva y se
confirma empíricamente con 2/2 aciertos en HTTP puro.

### 3. Scrapling 0.4.15 es viable como capa de transporte
- Compatible con Python 3.14 ✓
- `FetcherSession` con cookie jar persistente e impersonation TLS (usa curl_cffi internamente)
- Parser CSS propio funcional; API: `sel.css()` → `Selectors`, `.attrib`, `.get_all_text()`
- `StealthySession` funciona headless (Chromium ya descargado; `install-deps` falló sin
  sudo pero no hizo falta)
- Sobrecoste del browser: ~30s/página vs ~instantáneo en HTTP → para nuestro volumen,
  **HTTP+warming basta; stealth queda como escalada de fallback**

### 4. ⚠️ InfoJobs cambió su DOM (independiente del PoC)
La clase `.ij-OfferDetailDescription` (fallback del parser de producción) **ya no existe**
en el HTML actual. Verificado offline contra snapshots del PoC:

```
InfoJobsParser.parse_detail_html(results/t2_detail_*.html)  →  ✅ parsea perfecto
title/company/city/work_mode/salary/exp_min/edu/skills/desc  →  todos correctos
```

El selector primario (`section.ij-OfferDetailPage-mainContent`) sigue vivo, así que
el pipeline de producción **probablemente sigue funcionando hoy**, pero el fallback
está muerto. Riesgo latente si el primario cambia.

## Veredicto

**Scrapling adoptable SIN proxies.** La ruta recomendada combina ambos hallazgos:

1. Transporte: `FetcherSession` + patrón warming (ya validado en T2)
2. Escalada: solo si reaparece decoy → `StealthySession` (validado en T3)
3. Futuro: si vuelve el bloqueo por IP → `proxy=` nativo de Scrapling (Webshare/ISP)

## Artefactos

| Archivo | Contenido |
|---------|-----------|
| `results/t1_search.html` | Snapshot search page real |
| `results/t2_warm_search.html` / `t2_detail_{1,2}.html` | Snapshots flujo warmed HTTP |
| `results/t3_warm_search.html` / `t3_detail_{1,2}.html` | Snapshots flujo stealth |
| `results/t{1,2,3}_summary.json` | Métricas estructuradas por test |
