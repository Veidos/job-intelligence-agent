# ADR-008: Scoring determinista 0-1 con multiplicadores de nivel

**Fecha:** 2026-05-25
**Tipo:** `arquitectura`
**Estado:** `activo`
**Componente:** `src/pipeline/evaluate.py`, `src/pipeline/fetch.py`

---

## Contexto

El sistema de scoring anterior delegaba toda la evaluación numérica a gemma4:e4b:
- `evaluate_technical` devolvía 4 números (skills_hard_match 0-30, experience_match 0-20, education_match 0-10, location_match 0-5) y `evaluate_hr` devolvía 4 números (trajectory_coherence 0-15, recency_relevance 0-15, market_competitiveness 0-5) más una penalty 0-25.
- Cada prompt pedía al modelo razonar y emitir puntuaciones enteras con rango acotado, y Python las sumaba con pesos implícitos (30+20+10+5 + 15+15+5 - 25 = 100 pts).

Esto tenía problemas:
1. **Inconsistencia entre ofertas.** Misma skill, mismo nivel, distinto score porque el modelo podía ponderar distinto en diferentes llamadas (temperatura 0.1 en técnica).
2. **Caja negra.** Sin trazabilidad de por qué una skill puntuó X y no Y. El razonamiento del modelo era narrativo, no replicable.
3. **Penalización duplicada.** El gap laboral se penalizaba tanto en la penalty de HR como vía experience_match reducido, sin reglas claras.
4. **Salida no acotada a 0-1.** El score 0-100 se mapeaba a ratings discretos, pero los rangos eran arbitrarios y no calibrados contra el perfil real.
5. **skills_required legacy.** La DB almacenaba skills_required como JSON flat array  sin nivel asociado, imposibilitando matching por nivel.

---

## Decisión

**Reemplazar el scoring narrativo del LLM por un modelo determinista 0-1 con multiplicadores de nivel, donde el LLM solo detecta presencia de skills y el contexto cultural, y Python computa el score con reglas fijas.**

El nuevo flujo por oferta:

1. `evaluate_technical()` — gemma4 detecta solo presencia/nivel de skills (temp 0.0). No devuelve números.
2. `compute_skill_score()` — Python calcula `M_core` y `M_sec` con `level_multiplier(candidate_level, required_level) = min(cand/req, 1.0)`. Si `required_level=None` → 1.0.
3. `compute_experience_score()` — Python calcula `F_exp = years_match * G(gap)`, con `GAP_MULTIPLIER` fijo.
4. `evaluate_hr()` — gemma4 devuelve solo `context_fit` (0.0-1.0), sin scores numéricos.
5. Score final: `S = 0.45*M_core + 0.15*M_sec + 0.25*F_exp + 0.15*F_fit`
6. `evaluate_final()` — igual que antes, valida relevance_flag y bloqueos.

### Esquema de skills_required

Ahora se almacena como JSON estructurado:

```json
{
  "core": [{"name": "Python", "level_required": "intermedio"}, ...],
  "secondary": [{"name": "Git", "level_required": null}, ...]
}
```

`parse_skills_required()` en fetch.py convierte automáticamente arrays legacy y otros formatos al nuevo esquema, garantizando backward compatibility.

### Tabla GAP_MULTIPLIER

| Gap (años) | Multiplicador |
|------------|---------------|
| 0 - 1      | 1.00          |
| 1 - 2      | 0.85          |
| 2 - 3      | 0.70          |
| 3 - 4      | 0.55          |
| 4+         | 0.40          |

Sin penalización narrativa del LLM. El gap se aplica como factor multiplicativo sobre `years_match`, no como resta arbitraria.

### Niveles

| Nivel | Ordinal |
|-------|---------|
| básico | 1 |
| intermedio | 2 |
| avanzado / experto | 3 |

`level_multiplier = min(ord(candidato), ord(requerido)) / ord(requerido)`. Sobrecualificación capped a 1.0.

---

## Alternativas descartadas

- **Seguir con scoring vía LLM.** Descartado por inconsistencia entre ofertas y falta de trazabilidad. El modelo decidía si penalizar o no según su estado, no según reglas fijas.
- **Sistema de puntos con tabla de correspondencias (ej. Python básico = 2 pts).** Descartado porque no escala a skills nuevas que el modelo puede inventar. El matching por substring + nivel permite cualquier skill.
- **Delegar todo a gemma4 con temperatura 0.0.** Descartado en ADR-006+: el LLM sigue siendo necesario para detección semántica de skills (sinónimos, equivalentes) y evaluación de contexto cultural. Pero la puntuación numérica debe ser determinista.
- **Mantener flat array en skills_required.** Descartado porque sin nivel asociado no se puede computar `level_multiplier`. La migración es automática vía `parse_skills_required`.

---

## Consecuencias

- **Scoring totalmente determinista y trazable.** `skill_detail` se almacena en `penalty_breakdown` con L_i individual por skill para auditoría.
- **El LLM ya no puede inventar puntuaciones.** Solo responde presente/ausente y nivel detectado. El peso lo pone Python.
- **Backward compatibility.** `parse_skills_required` maneja datos legacy (flat array, JSON string, None) sin migración de DB.
- **`education_match` y `location_match` se fijan a 0.** El modelo anterior ponderaba 10 pts educación y 5 pts ubicación con reglas imprecisas. Estos factores ahora son contexto cualitativo dentro de `context_fit` de HR.
- **`trajectory_coherence`, `recency_relevance`, `penalty` se fijan a 0.** El gap laboral se aplica como multiplicador determinista, no como resta. La coherencia de trayectoria es contexto cualitativo.
- **Score final en 0.0-1.0**, no 0-100. `match_score` en DB se almacena como `round(score * 100)` para compatibilidad con queries existentes.
- **171 tests actualizados y passing.**
- **Las columnas legacy de `offer_evaluations` se siguen escribiendo** con valores fijos (0 o None) para no romber queries existentes.

---

## Referencias

- ADR-006 — evaluate_final y eliminación del pre-filtro
- ADR-005 — Separación de ejes en classifier (patrón: LLM razona + Python decide)
- docs/RATING.md — sistema de puntuación (obsoleto, pendiente de actualización)
- docs/CONVENTIONS.md — fases de implementación (Fase 4 completa)
