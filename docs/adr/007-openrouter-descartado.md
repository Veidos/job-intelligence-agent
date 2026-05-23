# ADR-007: OpenRouter descartado como backend alternativo

**Fecha:** 2026-05-23
**Tipo:** `reversión`
**Estado:** `activo`
**Componente:** `src/utils/openrouter_client.py`

---

## Contexto

Se evaluó OpenRouter (vía `openrouter/free`) como backend LLM alternativo
a Ollama para eliminar la dependencia del modelo local gemma4:e4b.

Se implementó `openrouter_client.py` con la misma interfaz que
`ollama_client.py`, un resolver por backend en `evaluate.py`,
`role_classifier.py` y `run.py`, y se extrajo `_extract_json` a
`json_utils.py` para compartirlo entre ambos clientes.

## Decisión

**Descartar OpenRouter.** gemma4:e4b (Ollama local) es más fiable
y produce resultados consistentes.

## Datos de la evaluación

Se ejecutaron 6 de 17 ofertas T-4 con OpenRouter antes de abortar:

| Oferta | Ollama | OpenRouter | Δ |
|--------|--------|-----------|---|
| Analista-Programador Junior | 53 | 30 | -23 |
| Analista Datos (Looker) | 61 | 33 | -28 |
| Analista bases de datos | 12 | 33 | +21 |
| Analista Datos y Automatización | 61 | 35 | -26 |
| Analista Power BI Junior | 43 | 43 | 0 |
| Data Analyst (SQL, Python, PBI) | 41 | 43 | +2 |

**Problemas detectados:**
- `openrouter/free` enruta a modelos distintos por llamada → scores inconsistentes
- Extracción JSON falla intermitentemente (modelo devuelve texto plano)
- Error `NoneType.strip` por respuesta vacía en 1 oferta
- Score medio 7pts menor que Ollama en ofertas comparables

## Consecuencias

- Revertidos los commits `0db3749` y `cb54a4f`
- `openrouter_client.py` y `json_utils.py` eliminados
- `ollama_client.py`, `evaluate.py`, `role_classifier.py`, `run.py`
  vuelven a su estado pre-OpenRouter
- `.env.example` vuelve a su estado anterior (sin vars OpenRouter)
- Si en futuro se explora un backend remoto, debe usar un modelo concreto
  (ej. `openai/gpt-4o-mini`) con presupuesto asignado, no un router automático

## Referencias

- ADR-006 — evaluate_final (último ADR antes de este revert)
- `reports/testing/06-evaluate-openrouter.html` — reporte comparativo
- `scripts/reporte_evaluate_v2.py` — script del reporte
