# ADR-006: evaluate.py — tercer prompt (evaluate_final) y eliminación del pre-filtro

**Fecha:** 2026-05-23
**Tipo:** `arquitectura`
**Estado:** `activo`
**Componente:** `src/pipeline/evaluate.py`

---

## Contexto

El pipeline de evaluación ejecutaba dos prompts por oferta (técnico + HR) precedidos
de un pre-filtro que llamaba a gemma4 para detectar requisitos estructuralmente
imposibles. Si el pre-filtro descartaba la oferta, se guardaba con `match_score=0`
y `descarte_tipo="requisito_imposible"`, saltándose la evaluación real.

Esto tenía dos problemas:

1. **Pérdida de información.** Una oferta con bloqueo legal (ej. prácticas universitarias)
   pero buen match técnico (score ~70) quedaba registrada como score=0, invisible
   para el análisis de mercado y la validación humana.
2. **Duplicidad de responsabilidad.** El pre-filtro y la penalty de HR evaluaban
   conceptos similares (bloqueos de aplicación) desde prompts distintos, con riesgo
   de incoherencia.
3. **Sin validación del classifier.** No existía un paso que contrastara el
   `relevance_flag` asignado por `role_classifier` contra la descripción completa
   y las evaluaciones.

---

## Decisión

**Eliminar el pre-filtro temprano (`check_impossible_requirements`) y añadir un
tercer prompt (`evaluate_final`) que se ejecuta después de technical+HR, con
temperatura=0.0, para validar el relevance_flag y detectar bloqueos de aplicación
con toda la información disponible (descripción + evaluaciones + score).**

El nuevo flujo por oferta es:

1. `evaluate_technical()` — gemma4, temp 0.1 (bloque A, 60 pts)
2. `evaluate_hr()` — gemma4, temp 0.0 (bloque B + penalty, 40 pts)
3. Cálculo de `match_score` = `max(0, min(100, bloque_A + bloque_B - penalty))`
4. `evaluate_final()` — gemma4, temp 0.0 (validación + bloqueos, no altera score)
5. `save_evaluation()` con las 6 columnas nuevas

Campos añadidos a `offer_evaluations`:

| Columna | Propósito |
|---------|-----------|
| `relevance_validation` | `confirmed` o `corrected` — validación del relevance_flag del classifier |
| `relevance_corrected` | Valor corregido si aplica |
| `relevance_reasoning` | Explicación breve de la validación |
| `apply_block` | `requisito_imposible`, `practicas`, `otro` o `null` |
| `apply_block_reason` | Explicación del bloqueo |
| `llm_apply_signal` | `yes/maybe/no` del LLM (independiente del rating numérico) |

Lo que **no cambia**:
- `recommendation` sigue siendo `get_rating(raw_score)` — rating basado en score
- `apply_recommendation` (columna existente) no se toca — preserva datos históricos
- `offers.relevance_flag` no se modifica desde evaluate.py — el flag del classifier
  es la verdad histórica; `relevance_corrected` es una segunda opinión

---

## Alternativas descartadas

- **Mantener el pre-filtro como paso temprano.** Descartado porque descartar con
  score=0 destruye información de mercado. El coste de 2 llamadas extra por oferta
  descartable (~15-50 ofertas/día) es asumible frente al beneficio de tener el
  score real de todas las ofertas.
- **Fusionar evaluate_final con evaluate_hr.** Descartado porque mezclar validación
  de clasificación con evaluación HR contamina ambos juicios. Separando los prompts
  cada uno tiene un objetivo claro y temperatura independiente.
- **Usar el campo `apply_recommendation` existente para el signal del LLM.**
  Descartado por ruptura semántica con datos históricos. Se crea `llm_apply_signal`.

---

## Consecuencias

- **Toda oferta evaluada tiene score real**, incluso las bloqueadas. Permite
  validación humana (T-5) y análisis de mercado sobre ofertas con bloqueo.
- **Tres llamadas a gemma4 por oferta** en lugar de 1-2. Asumible para el volumen
  diario del pipeline.
- **Las columnas `descarte_tipo` y `descarte_razon` dejan de escribirse** (no se
  eliminan físicamente por limitaciones de SQLite). Los datos históricos se
  preservan.
- **El relevance_flag del classifier ahora tiene contraste.** `relevance_corrected`
  permite medir calidad del classifier a posteriori.
- **Tests actualizados:** 3 tests del pre-filtro eliminados, 5 actualizados para
  el tercer mock. 171 tests passing.
- **Nueva columna `llm_apply_signal`** añadida al schema. Cualquier consumidor
  futuro debe decidir si usa `recommendation` (rating numérico) o `llm_apply_signal`
  (juicio del LLM).

---

## Referencias

- PRD 5.2.3 — Evaluación HR con penalización
- ADR-005 — Separación de ejes en classifier (mismo patrón: el LLM razona,
  Python decide)
