# 004 — Aplazar testing T-2 por límite de API Apify

**Fecha:** 2026-05-22
**Tipo:** `operativo`
**Estado:** `activo`

## Contexto

El test T-2 (fetch.py con `sinceDate=_24_HOURS` en producción real) requiere
ejecutar el actor Apify `lRxJmbuhggr0LU3uj`. Al intentarlo se obtuvo el error:

> `Monthly usage hard limit exceeded`

El plan FREE de Apify tiene 5 USD/mes de crédito. Se agotó durante los
desarrollos previos (último fetch real: 2026-05-19). Quedan 0.30€ pero el
límite duro mensual impide cualquier ejecución, incluso con `maxItems=3`.

## Decisión

Aplazar T-2 hasta el próximo ciclo de facturación de Apify (junio 2026).
Continuar con T-3 a T-9 usando las 147 ofertas existentes en DB y Ollama local.

## Alternativas descartadas

- **Pagar plan superior:** no justificado para testing del MVP, el FREE
  cubre el uso normal del pipeline (~2-3 USD/mes).
- **Cambiar a otra fuente de datos (Indeed, LinkedIn, Jobicy):** requiere
  desarrollo nuevo de adapter. No es viable para testing de lo ya construido.
- **Forzar test con otro actor Apify:** el límite es por cuenta, no por actor.

## Consecuencias

- T-2 queda en estado ⏳ pendiente, no ❌ fallido.
- El pipeline real no se ha validado end-to-end con fetch real contra InfoJobs.
- La deduplicación por `source_id` ya se probó con 147 offers en DB.
- `build_search_urls` y el parámetro `sinceDate` se validan a nivel unit test
  con cassettes (test_fetch_cassettes.py).
- En junio 2026 se retoma T-2 con prioridad antes de cualquier nuevo fetch.
