# 025 — Fichas de detalle por navegador real (InfoJobs exige JavaScript)

**Date:** 2026-10-05
**Type:** `architecture` `dependency`
**Status:** `active`

## Context

El run `search_runs.id=41` (2026-10-05) devolvió **0 ofertas**: las 6 fichas de detalle
recibieron el muro de Distil Networks ("No podemos identificar tu navegador", HTTP 200,
~29 KB, mismo `content_hash`). El navegador de Camoufox recupera las mismas fichas sin
problema, lo que demuestra que el reto es de JavaScript, no de reputación de IP.

El muro existía en la base de datos desde antes, pero **nunca se detectaba**:

- `InfoJobsParser._is_decoy_page()` solo recorría `html[:2000]`.
- El aviso real está en el índice **18.149** del HTML de 29.738 bytes.
- Conclusión: el transporte creía que cada muro era una oferta válida, así que
  `_consecutive_decoys` nunca subía, nunca se alcanzaba `MAX_CONSECUTIVE_DECOYS=2` y
  `StealthySession` (Camoufox) **nunca se lanzaba**.
- Los tests cubrían el cortacircuito, pero con un decoy sintético de 97 bytes con la
  frase en el índice 0: CI en verde y producción rota.

Los datos del bronze demuestran que InfoJobs endureció la protección de detalle:

| Run | Fichas por HTTP | Muros |
|---|---|---|
| 26 ago – 1 sep (6 runs) | 141 | 0 |
| 5 oct | 6 | **6 (100%)** |

Además `search()` no detectaba muros: `parse_search_html()` devolvía `[]` y el código
asumía "página sin resultados", cortando la keyword sin reintentar.

## Decision

Las fichas de detalle se descargan **siempre por navegador real (Camoufox)**, con
`SCRAPER_DETAIL_MODE=stealth` como valor por defecto; las búsquedas siguen por HTTP
barato y reintentan por navegador si reciben el muro.

## Discarded alternatives

- **Proxy residencial rotatorio.** Es lo que proponía `MEMORIES.md` para bloqueos por
  IP, pero aquí el bloqueo no es de IP: Camoufox pasa desde la misma IP. Es gasto
  mensual injustificado.
- **Esperar a que Distil relaje el muro.** Sin plazo conocido y sin garantía.
- **Volver a Apify (ADR-016).** Degradaba el parseo: 1-2 skills frente a 8+, y
  `experience_min` siempre 0. ~$2,70/mes.
- **Subir el fingerprint TLS** (`chrome131` → `chrome150`, disponible en curl_cffi
  0.16.2). Probado: el muro es idéntico (29.738 chars). El pin obsoleto sigue siendo
  un bug latente de maintenance, no la causa.
- **Escalar solo tras 2 decoys (diseño original).** Funciona, pero paga una petición
  HTTP perdida por ficha. Con el reto de JS ya obligatorio en detalle, es un Peaje
  innecesario.

## Consequences

- Coste medido (oct-2026): arranque de Camoufox 0,5 s (amortizable dentro del run),
  ficha 4,7 s, búsqueda HTTP 0,4 s, memoria del navegador ~173 MB. Un run de 30 fichas
  pasa de ~1 min a ~3 min.
- Si el navegador no arranca, `_fetch_detail` degrada a HTTP con warning en lugar de
  abortar el run.
- `SCRAPER_DETAIL_MODE=auto` conserva el comportamiento antiguo por si InfoJobs
  relajara la protección; `http` sirve de diagnóstico.
- La detección de muro recorre 60 KB en vez de 2.000. Coste despreciable y verificado
  sin falsos positivos sobre 141 fichas y 81 búsquedas reales del bronze.
- `IMPERSONATE="chrome131"` queda obsoleto (curl_cffi 0.16.2 admite hasta `chrome150`).
  Pendiente: actualizar cuando se verifique que no cambia la huella de forma que afecte a la bolsa.