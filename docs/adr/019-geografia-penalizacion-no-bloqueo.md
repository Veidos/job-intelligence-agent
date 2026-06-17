# ADR-019: Geografía — penalización determinista, no bloqueo ni componente de F_fit

**Date:** 2026-06-17
**Status:** active
**Component:** src/pipeline/evaluate.py → evaluate_hr(), evaluate_final()

## Contexto

El sistema tiene dos representaciones de la geografía que producen comportamiento incoherente:

1. **`location_match` (determinista):** calcula 0.0–1.0 según modalidad y ciudad.
   Se guarda en DB pero **no entra en la fórmula final**
   `S = 0.45·M_core + 0.15·M_sec + 0.25·F_exp + 0.15·F_fit`. Es solo informativo.

2. **`F_fit` contaminado (no determinista):** el prompt `evaluate_hr()` pasaba ciudad y
   modalidad de la oferta a gemma4, y preguntaba "¿La modalidad y ubicación son viables?".
   El LLM incorporaba esa señal en `context_fit`, que sí pesa 15% en la fórmula.
   La incompatibilidad geográfica penalizaba de forma opaca e irreproducible.

3. **`apply_block` geográfico (error LLM):** en algunos casos `evaluate_final()` clasificaba
   incompatibilidades geográficas como `apply_block = "requisito_imposible"`, eliminando
   la oferta antes de que el candidato pudiera verla. Incorrecto: la geografía es negociable.

## Decisión

**La geografía se modela ÚNICAMENTE a través de `location_match` (determinista).
`F_fit` queda exclusivamente para cultura, sector, fit personal y entorno laboral.
`apply_block` nunca se usa para incompatibilidades geográficas.**

### Cambio 1 — evaluate_hr(): eliminar pregunta geográfica + instrucción negativa

Eliminar del prompt:
- La línea `Ubicación: {offer.get("city")} | Modalidad: ...` (datos de contexto)
- La pregunta `¿La modalidad y ubicación son viables?`

Añadir instrucción negativa explícita antes del bloque JSON:
```
NO penalices ubicación ni modalidad en context_fit. La geografía ya está
capturada en otro componente del score. Evalúa SOLO cultura, sector y fit personal.
```

La instrucción negativa es necesaria porque gemma4 ve la ciudad del candidato y la
de la oferta en el contexto, e infiere el mismatch sin que se le pregunte.

### Cambio 2 — evaluate_final(): añadir geografía a "no son bloqueos"

Añadir a la lista:
```
incompatibilidad geográfica o de modalidad (ya capturada en location_match)
preferencia de la empresa por candidatos locales
```

## Verificación

El scatter `M_core vs F_fit` en el dashboard Pipeline es el indicador:
- Puntos dispersos → F_fit aporta señal independiente (cultura/sector). Fix funcionó.
- Puntos en diagonal → F_fit sigue covariando con M_core. Fix incompleto.

## Consecuencias

- `F_fit` mide exclusivamente cultura, sector y fit personal. Trazable y auditable.
- `location_match` sigue siendo informativo sin peso en la fórmula. Promocionarlo
  a componente con peso explícito es deuda técnica documentada (ver ADR-008).
- Evaluaciones anteriores a este commit tienen `F_fit` potencialmente contaminado
  por geografía. No se re-evalúan; se documentan como datos históricos con sesgo conocido.
- El candidato decide la cuestión geográfica con información completa, no filtrada.

## Referencias

- ADR-008 — [Scoring determinista con multiplicadores](008-scoring-determinista-con-multiplicadores.md)
- ADR-006 — [evaluate_final prompt (bloqueos reales)](006-evaluate-final-prompt.md)
- ADR-013 — [Scoring rebalance v2](013-scoring-rebalance-v2.md)
