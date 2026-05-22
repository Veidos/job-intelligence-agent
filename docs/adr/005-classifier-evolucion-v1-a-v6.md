# ADR-005: Role Classifier — Evolución v1 → v6 y decisiones de diseño

**Fecha:** 2026-05-22
**Estado:** Aceptado
**Componente:** `src/pipeline/role_classifier.py`
**Módulo de reporte:** `scripts/reporte_v6.py`

---

## Contexto

El clasificador de roles es el componente central del pipeline de inteligencia de empleo. Su función es doble: (1) asignar un `role_normalized` canónico a cada oferta scrapeada, y (2) evaluar el fit del candidato mediante `relevance_flag` (`core / adjacent / stretch / temporal`) y `gap_type` (`seniority / dominio / herramienta / estructural / none`).

El sistema usa **gemma4:e4b** vía Ollama (`/api/generate`, prompt único por llamada, sin historial acumulado entre ofertas). Dada la limitación del modelo local, el principio de diseño adoptado es: **el modelo razona, Python decide**. Todo lo verificable determinísticamente vive en código, no en el prompt.

---

## Historial de versiones

### v1 — Baseline

**Problema:** Colapso total a `relevance_flag: core`. 16 de 17 ofertas clasificadas como `core`, 1 como `adjacent`.

**Causa raíz:** El prompt no tenía estructura de decisión explícita. El modelo resolvía la ambigüedad hacia el valor más optimista.

**Distribución:** `core: 16 / adjacent: 1 / stretch: 0 / temporal: 0`

---

### v2 — Prompt refactorizado (FASE 1 / FASE 2)

**Cambio:** Separación del razonamiento en dos fases: (1) clasificación del rol objetivo, (2) evaluación del fit del candidato.

**Resultado:** Distribución razonable: `adjacent: 8 / stretch: 9`. Eliminación del sesgo hacia `core`.

**Problema residual:** `gap_types` devuelto como lista de dicts en vez de string, provocando error `unhashable type: dict` en `resolve_gap_type`.

---

### v4 — Fix del bug unhashable

**Cambio:** `resolve_gap_type` corregido para manejar lista de dicts.

**Regresión introducida:** El prompt reestructurado hizo que gemma4 devolviera `gap_types: []` (vacío) en la mayoría de llamadas. Por jerarquía, `[]` → `none` → `core`. Colapso total de nuevo.

**Distribución:** `core: 16 / stretch: 1`

**Lección:** Un fix de parsing no debe alterar la estructura del prompt. Los cambios deben ser atómicos.

---

### v5 — Versión estable

**Cambio:** Restauración del prompt a la estructura v2 con el fix de parsing de v4 aplicado correctamente.

**Resultado:** `adjacent: 8 / stretch: 9 / core: 0`. Distribución sana y consistente con v2.

**Evaluación de corrección (13/17):**

| ID | Oferta | Flag v5 | Flag esperado | ¿Correcto? |
|----|--------|---------|---------------|-----------|
| 226 | Looker Quest | stretch/seniority | adjacent/herramienta | ⚠️ |
| 227 | Izertis BD | stretch/seniority | stretch/seniority | ✅ |
| 228 | New Tandem | adjacent/dominio | adjacent/herramienta | ⚠️ |
| 229 | NTT Junior PBI | stretch/seniority | adjacent/herramienta | ⚠️ |
| 230 | EY Internship | adjacent/dominio | adjacent/dominio | ✅ |
| 231 | BETWEEN SQL/PBI | adjacent/herramienta | adjacent/herramienta | ✅ |
| 232 | Barcel RRHH | stretch/seniority | stretch/seniority | ✅ |
| 233 | DABA Sant Cugat | stretch/seniority | stretch/seniority | ✅ |
| 234 | Indra Compliance | stretch/seniority | estructural/seniority | ⚠️ |
| 235 | HomeServe | adjacent/herramienta | adjacent/herramienta | ✅ |
| 236 | Embragues | stretch/seniority | stretch/seniority | ✅ |
| 237 | BETWEEN PBI Reporting | stretch/seniority | stretch/seniority | ✅ |
| 238 | Grupo Crit Power Platform | adjacent/herramienta | adjacent/herramienta | ✅ |
| 239 | Automoción Junior | adjacent/dominio | adjacent/dominio | ✅ |
| 240 | HOGAR SÍ Consultoría | stretch/seniority | stretch/seniority | ✅ |
| 241 | Softtek Ecommerce | adjacent/dominio | adjacent/dominio | ✅ |
| 242 | Auxitec Junior | adjacent/herramienta | adjacent/herramienta | ✅ |

**Roles incorrectos detectados (ruido del modelo):**
- ID 227 (Izertis): clasificado como `data_engineer`. Debería ser `bi_analyst` o perfil técnico híbrido. El catálogo no tiene un rol intermedio entre `data_analyst` y `data_engineer`.
- ID 236 (Embragues): clasificado como `data_scientist`. El núcleo es EDA + reporting. ML aparece como secundario.
- ID 240 (HOGAR SÍ): clasificado como `data_scientist`. El núcleo es consultoría + gobierno del dato. Asumido como ruido del modelo local y aceptado como limitación de gemma4:e4b.

---

### v6 — `is_new_role` determinista + trazabilidad

**Problema detectado:** `trade_compliance_specialist` (ID 234) no estaba en el catálogo aunque era un rol nuevo. El modelo devolvió `is_new_role: false` cuando debía ser `true`. El mecanismo de catálogo dinámico dependía de que el modelo fuera honesto sobre si el rol era nuevo — lo cual no es fiable.

**Verificación:**
```sql
SELECT role_catalog FROM search_config ORDER BY id DESC LIMIT 1;
-- Resultado: 17 roles, sin trade_compliance_specialist
```

**Decisión:** Reemplazar la lógica basada en el LLM por verificación determinista en Python.

**Cambios implementados:**

1. **`src/pipeline/role_classifier.py`** — `_run_logic`:
   ```python
   # Antes (confiaba en el modelo):
   is_new_role = result["is_new_role"]
   if is_new_role and role_normalized not in catalog:

   # Después (determinista):
   is_new_role = role_normalized not in catalog
   result["is_new_role"] = is_new_role
   if is_new_role:
   ```

2. **`src/db/schema.sql`** — columna añadida:
   ```sql
   ALTER TABLE offers ADD COLUMN is_new_role INTEGER DEFAULT 0;
   ```

3. **`src/db/migrate.py`** — migración correspondiente añadida.

4. **UPDATE SQL en el pipeline** — `is_new_role` ahora se persiste en cada clasificación.

**Resultado:** `trade_compliance_specialist` detectado automáticamente. Catálogo actualizado a 18 roles. Distribución idéntica a v5: `adjacent: 8 / stretch: 9`.

**Bug de orden en HTML (detectado y resuelto):** Las ofertas ID 241 y 242 aparecían en orden incorrecto en el HTML generado (240 → 242 → 241) por ausencia de `ORDER BY id ASC` en la query de los scripts generadores. Fix aplicado en todos los scripts (`reporte_v3.py`–`reporte_v6.py`, `comparativa_classifier.py`) y HTMLs generados. Commits `c7f3d1a` y `b26cb03`.

---

## Decisiones de diseño adoptadas

### 1. El modelo razona, Python decide

Todo lo verificable con lógica determinista vive en código, no en el prompt:
- Detección de roles nuevos: `role_normalized not in catalog`
- Jerarquía de gap_types: lógica de prioridad en `resolve_gap_type`
- Validación de campos requeridos en el JSON de respuesta

**Motivación:** gemma4:e4b es un modelo pequeño en local. Su fiabilidad en decisiones binarias estructurales (¿es este rol nuevo?) es inferior a O(n) en Python.

### 2. Cambios atómicos en el prompt

v4 demostró que combinar un fix de parsing con una reestructuración del prompt produce regresiones difíciles de aislar. Cada cambio debe afectar exactamente una variable.

### 3. Separación de ejes de decisión

El clasificador opera sobre dos ejes independientes:
- **Tipo de rol objetivo:** qué es esta oferta en el mercado, objetivamente.
- **Fit del candidato:** qué tan cerca está el candidato de ese rol.

Mezclar ambos ejes en un único razonamiento contamina la clasificación. El prompt v5/v6 mantiene esta separación en FASE 1 y FASE 2.

### 4. Trazabilidad siempre

Cualquier campo calculado en el pipeline debe persistirse en DB. `is_new_role` fue el primer caso en que esto no ocurría. La regla es: si se calcula, se guarda.

---

## Limitaciones conocidas y aceptadas

| Limitación | Impacto | Decisión |
|---|---|---|
| Roles frontera inflados a `data_scientist` / `data_engineer` | IDs 227, 236, 240 | Aceptado como ruido de gemma4:e4b. Revisable con modelo superior. |
| `estructural` no usado en práctica | ID 234 clasificado como `stretch` cuando debería ser `structural` | El modelo no discrimina `estructural` de `stretch` con fiabilidad. Pendiente de mejora de prompt o modelo. |
| Catálogo sin `bi_analyst` como rol intermedio | Fuerza clasificaciones a `data_analyst` o `data_engineer` en perfiles híbridos | Pendiente de revisión del catálogo de roles. |

---

## Estado actual del catálogo (post-v6)

18 roles: `data_analyst`, `data_scientist`, `ml_engineer`, `bi_analyst`, `data_engineer`, `operations_analyst`, `quality_analyst`, `process_engineer`, `technical_support`, `temporal`, `real_estate_consultant`, `martech_consultant`, `erp_consultant`, `it_consultant`, `recruitment_specialist`, `b2b_sales_representative`, `market_research_analyst`, **`trade_compliance_specialist`** *(nuevo en v6)*.
