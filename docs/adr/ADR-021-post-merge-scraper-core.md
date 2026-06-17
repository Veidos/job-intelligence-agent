# ADR-021: Post-merge — skills del scraper siempre en core

- **Estado:** Activo
- **Fecha:** 2026-06-17

## Contexto

El scraper de InfoJobs extrae skills de la sección `<dl>` "Conocimientos" del
HTML de detalle. Estas skills son requisitos **explícitos** del empleador —
campos estructurados del formulario de la oferta.

Paralelamente, `extract_fields_with_llm()` (Fix 2, ADR-020) usa gemma4:e4b
para enriquecer la oferta desde la descripción libre, clasificando skills en
`core` y `secondary`. El problema: el LLM puede reclasificar una skill del
`<dl>` como secondary (ej. `"Entity Framework"` del scraper → `"EntityFramework"`
en secondary del LLM), diluyendo su peso en el score (`W_SEC=0.15` vs
`W_CORE=0.45`).

Esto es incorrecto por diseño: una skill que el empleador puso explícitamente
como requisito estructurado no es "deseable" — es obligatoria.

## Decisión

Aplicar **post-merge determinista** después del LLM: las skills del scraper
(`detail.skills`) son siempre core. El LLM no puede moverlas a secondary ni
omitirlas.

```python
def _merge_scraper_skills_into_llm(
    detail_skills: list[str],
    llm_skills: dict,
) -> dict:
```

Reglas:
1. Skill del scraper en LLM secondary → mover a core
2. Skill del scraper ausente en LLM → añadir a core
3. Secondary del LLM sin coincidencia en scraper → conservar

### Normalización

Para robustez frente a variaciones whitespace/guiones entre scraper y LLM
(ej. "Power BI" vs "PowerBI", "Scikit-learn" vs "sklearn"), se normaliza
antes del match:

```python
def _norm(name: str) -> str:
    return re.sub(r"[\s\-_./]", "", name.strip().lower())
```

El nombre que persiste en core es siempre el original del scraper
(`original_name` en el dict `scraper_normalized`), no la versión del LLM.

## Consecuencias

- Skills del `<dl>` nunca se pierden ni se degradan a secondary —
  siempre cuentan con `W_CORE=0.45` (o `W_CORE=0.60` si secondary vacío,
  ver ADR-020).
- El LLM sigue siendo libre de clasificar skills que solo aparecen en la
  descripción libre como core o secondary — el merge solo protege las que
  vienen del `<dl>`.
- Si el LLM devuelve vacío (`try/except`), el fallback base_skills ya pone
  todo el scraper en core — el merge refuerza este comportamiento.
- La normalización es conservadora: prefiere duplicados con nombres
  ligeramente distintos a perder un match real. Si el scraper tiene
  "Entity Framework" y el LLM "EntityFramework", el match se resuelve y
  el nombre del scraper gana.
- Tests: 6 casos (3 funcionales + 3 edge) en `test_fetch_merge_skills.py`.
