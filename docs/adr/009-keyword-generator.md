# ADR-009: Keyword Generator with Manual Curation

**Date:** 2026-05-27
**Type:** `architecture`
**Status:** `active`
**Component:** `src/onboarding/keyword_generator.py`

---

## Context

The pipeline's `fetch.py` consumes `search_config.role_hierarchy` to build
search URLs for Apify. Before ADR-009, this field was populated manually or
not at all — there was no systematic tool to generate search keywords from
the candidate profile (`PERFIL.md`).

The LLM (gemma4:e4b) is capable of suggesting relevant job titles, but:
1. Suggestions need human validation before they affect real pipeline runs
2. Keywords must match real InfoJobs taxonomy (not literal translations)
3. The user may want to add custom keywords not suggested by the model
4. Full automation is risky — bad keywords waste Apify API credits

---

## Decision

**Create `src/onboarding/keyword_generator.py` with three modes:**

### `run()` — Generate from PERFIL.md

1. Reads `PERFIL.md`
2. Calls gemma4:e4b with a rule-based prompt (no hardcoded titles)
3. Saves up to `MAX_KEYWORDS` (configurable) suggestions to `search_config.role_hierarchy`
4. Updates existing `search_config` row (preserves `geo_hierarchy`)

### `--dry-run` — Preview without saving

LLM is called, suggestions are printed to stdout, nothing is written to DB.

### `--manage` — Interactive curation

1. Shows current keywords with index numbers
2. Prompts: "Números a conservar (ej: 1 2 4 6 8)" — keep by number
3. Prompts: "Keywords a añadir" — add new ones manually
4. Saves to DB only on explicit confirmation

### Prompt design (200% rules, 0% hardcode)

```
USER_PROMPT_TEMPLATE = """Analiza este perfil profesional y genera los títulos de
puesto que una empresa española publicaría en InfoJobs para contratar a este candidato.
...
Reglas estrictas:
- Exactamente {max_kw} títulos únicos, sin variantes del mismo rol
- Sin indicadores de seniority (nada de Junior, Senior, Trainee, Mid)
- Incluye versiones en inglés Y en español de los roles principales
- Cubre áreas distintas del perfil
- Ordena de MÁS a MENOS volumen de ofertas reales en InfoJobs España
- Usa el nombre base del rol, sin adjetivos ni especializaciones innecesarias
- Usa únicamente títulos que existan realmente en InfoJobs España
Devuelve SOLO este JSON, sin texto extra, sin markdown:
{{"keywords": ["título 1", "título 2", "título 3"]}}"""
```

No hardcoded titles. The model decides freely based on the candidate profile.

### Note on system prompt

`ollama_call()` does not accept a `system` parameter. The system prompt
is embedded directly in the user prompt before the instruction body.

### Note on think=True

`think=True` is passed to `ollama_call()` and forwarded to `_call_ollama_raw()`.
If Ollama returns a `think` field, it is logged. gemma4:e4b does not always
return this field — logging is purely informational.

---

## Discarded alternatives

- **Full automation (no human step).** Dangerous: bad keywords waste Apify
  credits and pollute the offer database with irrelevant results.
- **Hardcode keywords in a config file.** Brittle: every edit requires a code
  change. The LLM should suggest, the human decides.
- **Manual SQL updates to search_config.** Feasible but error-prone and
  requires knowing the exact JSON structure.
- **Store keywords in a separate config file (YAML/JSON).** Adds an extra file
  to manage when `search_config` already exists in the DB for this purpose.

---

## Consequences

- **Keyword generation is decoupled from the pipeline.** No need to rerun
  onboarding to change search terms.
- **`--manage` allows surgical corrections** without rerunning the LLM.
- **Prompt changes don't affect existing keywords.** The user must explicitly
  regenerate (`run()`) to get new suggestions.
- **`MAX_KEYWORDS` controls LLM output breadth.** Set to 8, adjustable.
  `generate_keywords()` deduplicates results post-LLM as a safety layer.
- **System prompt inlining works** but means the prompt template and system
  role are coupled. If `ollama_call()` gains a `system` parameter in the
  future, `keyword_generator.py` should be updated to use it.
- **No changes to `fetch.py`** — it consumes `search_config.role_hierarchy`
  unchanged.

---

## References

- ADR-001 — ADR as a decision documentation system
- `src/onboarding/keyword_generator.py` — implementation
- `src/pipeline/fetch.py` — consumer of role_hierarchy
