# ADR-005: Role Classifier — decisiones de diseño y evolución v1 → v6

**Fecha:** 2026-05-22
**Tipo:** `arquitectura`
**Estado:** `activo`
**Componente:** `src/pipeline/role_classifier.py`
**Módulo de reporte:** `scripts/reporte_v6.py`

---

## Contexto

El clasificador de roles asigna a cada oferta scrapeada un `role_normalized` canónico y un `relevance_flag` (`core / adjacent / stretch / temporal`) con su `gap_type` (`seniority / dominio / herramienta / estructural / none`) que mide la distancia del candidato al rol. Opera con **gemma4:e4b** vía Ollama (prompt único, sin historial entre ofertas).

El desarrollo iterativo v1→v6 reveló tres problemas recurrentes:

1. **El modelo es optimista por defecto.** Sin estructura de decisión explícita, gemma4 clasifica toda oferta como `core` (v1: 16/17 core).
2. **Cambios acoplados en el prompt producen regresiones.** v4 introdujo un fix de parsing y una reestructuración del prompt en el mismo cambio, provocando un colapso silencioso a `core` que pasó desapercibido una jornada completa.
3. **El LLM no es fiable para decisiones binarias estructurales.** `is_new_role` devuelto por gemma4 dió un falso negativo en `trade_compliance_specialist`, impidiendo su incorporación al catálogo.

---

## Decisión

**Separar el razonamiento del clasificador en dos ejes independientes (FASE 1: rol objetivo, FASE 2: fit del candidato) y delegar al LLM exclusivamente el juicio semántico, mientras que toda decisión verificable determinísticamente (detección de roles nuevos, jerarquía de gap_types, validación de campos JSON) vive en código Python.**

Las cuatro reglas de diseño que gobiernan el clasificador desde v5/v6:

| Regla | Enunciado |
|-------|-----------|
| **El modelo razona, Python decide** | Detección de `is_new_role`, resolución de `gap_type`, validación de JSON → código. El LLM solo clasifica semánticamente. |
| **Cambios atómicos en el prompt** | Nunca combinar un fix de parsing con una reestructuración del prompt. Un cambio = una variable. |
| **Separación de ejes** | FASE 1 describe el puesto objetivamente; FASE 2 evalúa al candidato. Mezclarlos contamina ambos juicios. |
| **Trazabilidad siempre** | `is_new_role` demostró que los campos calculados no persistidos se pierden. Desde v6: si se calcula en el pipeline, se guarda en DB. |

---

## Alternativas descartadas

- **Prompt monolítico sin fases (v1).** Produce colapso a `core` por optimismo del modelo. Descartado por inviable.
- **Delegar `is_new_role` al LLM (v1–v5).** Falso negativo en `trade_compliance_specialist`. La fiabilidad del modelo local en decisiones binarias estructurales es inferior a `O(n)` en Python. Descartado.
- **Delegar `gap_type` entero al LLM (v1–v4).** Produce errores de formato (dicts en vez de strings) e inconsistencias. Descartado; la jerarquía se resuelve en `resolve_gap_type`.
- **Usar un modelo más grande (qwen2.5-coder:7b).** Probado y descartado durante desarrollo temprano (MEMORIES.md:87): no razonaba bien en contexto amplio. gemma4:e4b es el único modelo del pipeline.
- **No persistir `is_new_role`.** Cualquier campo calculado que no se guarda en DB se pierde al reprocesar. Descartado por violar trazabilidad.

---

## Consecuencias

- **La calidad del clasificador está acotada por gemma4:e4b.** Roles frontera (`data_scientist` vs `data_analyst`) y gap `estructural` tienen ruido aceptado como limitación del modelo local. Mejorable con modelo superior.
- **El catálogo de roles crece dinámicamente.** Cada nuevo `role_normalized` detectado se añade automáticamente. Requiere revisión periódica para evitar roles espurios o duplicados.
- **La regla "si se calcula, se guarda" es vinculante.** Cualquier nuevo campo derivado en el pipeline debe añadirse al schema y persistirse. Hay que mantener `ensure_columns_exist` y `migrate.py`.
- **El HTML generator debe preservar el orden por `id` ASC.** Bug detectado en v6 y corregido: los scripts usan `ORDER BY id` explícito.
- **Próximo paso natural:** mejorar el prompt para que discrimine `estructural` vs `stretch` con fiabilidad, y revisar si `bi_analyst` merece un slot propio en el catálogo.

---

## Anexo A: Historial de versiones

| Versión | Cambio | Distribución | Problema |
|---------|--------|-------------|----------|
| v1 | Baseline sin estructura de decisión | core:16 / adjacent:1 | Colapso por optimismo del modelo |
| v2 | FASE 1 + FASE 2 separadas | adjacent:8 / stretch:9 | gap_types como lista de dicts (error unhashable) |
| v4 | Fix unhashable + reestructuración prompt | core:16 / stretch:1 | Regresión por cambio acoplado |
| v5 | Prompt v2 restaurado + fix de parsing limpio | adjacent:8 / stretch:9 | Estable (13/17 correctos en evaluación manual) |
| v6 | `is_new_role` determinista en Python + columna en DB | adjacent:8 / stretch:9 | Catálogo crece a 18 roles; bug ORDER BY corregido |

## Anexo B: Evaluación de corrección v5/v6 (13/17)

| ID | Oferta | Flag asignado | Flag esperado | Correcto |
|----|--------|--------------|---------------|:--------:|
| 226 | Looker Quest Global | stretch / seniority | adjacent / herramienta | ⚠️ |
| 227 | Izertis BD | stretch / seniority | stretch / seniority | ✅ |
| 228 | New Tandem | adjacent / dominio | adjacent / herramienta | ⚠️ |
| 229 | NTT Junior PBI | stretch / seniority | adjacent / herramienta | ⚠️ |
| 230 | EY Internship | adjacent / dominio | adjacent / dominio | ✅ |
| 231–233, 235–242 | Resto | — | — | ✅ |

## Anexo C: Catálogo actual (18 roles)

`data_analyst`, `data_scientist`, `ml_engineer`, `bi_analyst`, `data_engineer`, `operations_analyst`, `quality_analyst`, `process_engineer`, `technical_support`, `temporal`, `real_estate_consultant`, `martech_consultant`, `erp_consultant`, `it_consultant`, `recruitment_specialist`, `b2b_sales_representative`, `market_research_analyst`, **`trade_compliance_specialist`** (nuevo en v6).
