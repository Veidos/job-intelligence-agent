# ADR-024: Grammar constraints vía Ollama `format` para outputs estructurados

**Date:** 2026-08-26
**Type:** `architecture`
**Status:** `active`
**Component:** `src/utils/llm_schemas.py`, `src/utils/ollama_client.py`, `src/pipeline/evaluate.py`

---

## Context

El pipeline de evaluación depende de que gemma4:e4b retorne JSON válido en 3 puntos críticos:
1. `evaluate_technical()` — skills presence + level detection
2. `evaluate_hr()` — context_fit + cultural assessment
3. `evaluate_final()` — relevance validation + decision

**Problemas observados:**
1. **JSON malformado ocasional** — gemma4 a veces envolvía output en fences markdown (` ```json ... ``` `), otros parsers fallaban
2. **Campos faltantes** — el modelo omitía `reasoning` o `skills_detected` sin pattern de error consistente
3. **Razonamiento como string "null"** — fix previo (ADR-014) eliminó `reasoning: "null"`, pero la causa raíz era falta de constraint estructural
4. **Sin trazabilidad de schemas** — los prompts describían el JSON esperado en lenguaje natural, pero sin enforcement

**Descubrimiento crítico durante PoC:**
- Ollama `format` parameter con `think=true` en gemma4:e4b **silencia la traza think** completamente
- Esto es comportamiento **pre-existente** desde junio (documentado en PLANS.md)
- El `think` field en el output desapareció sin causa identificada当时; ahora sabemos que es incompatibilidad con `format`
- `format=True` (bool) produce JSON crudo sin fences, misma velocidad (~23 tok/s)

---

## Decision

**Usar `format` de Ollama con JSON Schema estricto para los 3 bloques de evaluación, preservando el razonamiento obligatorio en campos required del schema.**

### Implementación

1. **`src/utils/llm_schemas.py`** — 3 schemas constantes:
   - `TECHNICAL_SCHEMA` — skills_detected (array con candidate_level nullable), experience_assessment, reasoning
   - `HR_SCHEMA` — context_fit, apply_signal, gap_severity, strengths/red_flags/hr_concerns/interview_prep
   - `FINAL_SCHEMA` — relevance_corrected (nullable), apply_block (nullable), seniority_adjustment, blockers_flag, relevance_reasoning

2. **`src/utils/ollama_client.py`** — `_call_ollama_raw()` acepta `json_schema: dict | None`:
   - Si se pasa: `payload["format"] = json_schema`
   - Si no se pasa: campo omitido (comportamiento previo)
   - `ollama_call()` propaga el parámetro + retry con instrucción de corrección

3. **`src/pipeline/evaluate.py`** — los 3 bloques usan su schema:
   ```python
   result = ollama_call(
       model=MODEL_TECHNICAL, prompt=prompt,
       expect_json=True, temperature=0.1, think=True,
       json_schema=TECHNICAL_SCHEMA,  # ← NUEVO
   )
   ```

### Diseño de schemas: permisivo vs estricto

| Aspecto | Decisión | Razón |
|---------|----------|-------|
| Strings libres (reasoning, verdict) | Sin `maxLength` | Respuestas variables, no forzar truncado |
| Arrays (strengths, red_flags) | Sin `minItems` | Arrays vacíos son válidos y significativos |
| Enums críticos (apply_signal) | `enum: ["yes","no","maybe"]` | Decisión binaria/ternaria,forzar consistencia |
| Tipos (context_fit) | `type: "number"` | Evitar que retorne string o null |
| Campos anulables | `type: ["string","null"]` | Eliminar clase del literal `"null"` como string |
| reasoning obligatorio | `required` incluye reasoning/verdict | "gemma4 nunca scores numéricos sin razonamiento" |

### Smoke test empírico (curl probes reales)

```
think=false + format=true  → JSON crudo válido, ~23 tok/s ✓
think=true  + format=true  → think silenciado, JSON válido ✓ (mismo resultado)
think=true  + format=false → JSON con fences, think intermitente
think=false + format=false → JSON con fences, sin think
```

**Conclusión:** `format=True` es seguro para todos los casos. El razonamiento exigible vive en campos `required` del schema, no en la traza think.

---

## Consequences

### Positivas
- **0 JSON parse failures** en run E2E #34 (43 llamadas LLM)
- **Output garantizado válido** — Ollama rechaza requests con schema inválido
- **Trazabilidad** — schemas documentan exactamente qué espera cada fase
- **Retry más efectivo** — el retry instruction se enfoca en contenido, no en formato

### Negativas
- **Pérdida de traza think** en gemma4 cuando se usa `format` — razonamiento interno no visible
- **Schemas acoplados al prompt** — cambios en prompts requieren actualizar schemas
- **Compatibilidad futura** — si Ollama cambia behavior de `format` + `think`, puede romper

### Mitigaciones
- El razonamiento exigible está en campos `required` (reasoning, verdict, relevance_reasoning)
- La traza think era intermitente desde junio — ya no dependemos de ella
- Monitorear `json_parse_failures` en `search_runs` para detectar regresiones

---

## Evidence

- Commit: `6ec33b3` — "Grammar constraints JSON vía Ollama format (ADR-024)"
- Tests: `tests/unit/test_llm_schemas.py` — 9 tests (estructura + payload)
- Run E2E #34: 43 calls, 0 JSON parse failures, 3 ofertas enviadas a Telegram
