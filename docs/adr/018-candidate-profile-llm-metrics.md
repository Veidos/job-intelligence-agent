# ADR-018: CandidateProfile, LLM Metrics, and location_match Status Quo

**Date:** 2026-06-11
**Type:** `architecture` `operational`
**Status:** `active`
**Component:** `src/utils/candidate_profile.py`, `src/utils/ollama_client.py`

---

## Context

Three independent decisions emerged during the quality fix session of 2026-06-11:

1. **Perfil parsing fragmentation:** `evaluate.py` parsed PERFIL.md with 4 independent regex calls (`load_skills_from_perfil`, `load_gap_from_perfil`, `load_experience_years_from_perfil`, `load_location_from_perfil`), each re-scanning the full text. Two prompts truncated the perfil by character position (`perfil[:2500]`, `perfil[:2000]`), which meant `personal_concerns` could be partially or fully excluded depending on file length.

2. **No LLM observability:** `ollama_call()` had no counters for reliability — impossible to know how often the model returned invalid JSON, empty responses, or how many total calls were made per pipeline run.

3. **location_match not in score formula:** `compute_location_score()` produces a 0.0-1.0 value persisted in DB but never included in the final score formula `S = W_CORE·M_core + W_SEC·M_sec + W_EXP·F_exp + W_FIT·F_fit`.

---

## Decision 1 — CandidateProfile unified parser

Create `src/utils/candidate_profile.py` with a `CandidateProfile` dataclass that:

- Parses ALL sections of PERFIL.md in a **single pass** using section-specific regex with `re.DOTALL | re.IGNORECASE` and lookahead `(?=\n##|\Z)`
- Stores all section content in `perfil_sections: dict[str, str]` (keyed by section name)
- Provides `skills_map`, `employment_gap`, `experience_years`, `city` as pre-parsed fields
- Provides `excerpt(section_names: list[str])` to compose prompt-specific excerpts without positional truncation

This eliminates position-based truncation (`perfil[:2500]`) and guarantees `personal_concerns` always reaches the HR LLM.

**Location:** `src/utils/candidate_profile.py` — shared between `evaluate.py` and future consumers (`role_classifier.py`).

**Backward compatibility:** Existing functions (`load_skills_from_perfil`, etc.) are preserved in `evaluate.py` for test coverage. `run_evaluate()` uses `CandidateProfile` directly.

---

## Decision 2 — LLM quality metrics

Add three counters to `src/utils/ollama_client.py`:

```python
_metrics = {
    "calls": 0,               # ollama_call() invocations
    "json_parse_failures": 0, # _extract_json() failures
    "empty_responses": 0,     # empty string from Ollama
}
```

Exposed via `get_llm_metrics()` and `reset_llm_metrics()`. Logged at pipeline end in `run.py` if calls > 0.

**Not counted:** `null_fields` (caller-specific, outside ollama_call's responsibility). `json_retries` (tenacity internal, not tracked separately).

**Not persisted:** Metrics are in-memory only. No new DB table — useful as runtime signal, not archival.

---

## Decision 3 — location_match status quo

`location_match` remains an **informational column** in `offer_evaluations`. It is NOT added to the score formula because:

- Location is not a binary hiring filter — a very good offer can justify relocation even if `location_match` is low
- `F_fit` (context_fit from HR LLM) already captures location qualitatively as part of environment evaluation
- The dashboard already exposes the column for user decision

Adding `W_LOC * location_match` would hardcode a heuristic that the user should evaluate case by case.

---

## Discarded alternatives

**For Decision 1:**
- Keeping position-based truncation: simple but fragile — `personal_concerns` location depends on file length
- Building per-section regex in each call site: duplicates parsing logic

**For Decision 2:**
- Persisting to a `llm_metrics` DB table: overengineered for runtime signal. Logging is sufficient for debugging.
- Counting per-prompt-type metrics: useful but ollama_call is agnostic of caller intent. Leave to callers.

**For Decision 3:**
- Adding `W_LOC * location_match` with a fixed weight (e.g., 0.10): arbitrary weight selection, would shift all scores without clear benefit. The ADR-013 rebalance intentionally excluded it.

---

## Consequences

- `personal_concerns` is guaranteed in HR LLM context (Decision 1)
- Perfil parsing is single-pass and extensible (new sections auto-detected via `_SECTION_PATTERNS`)
- Pipeline runs produce `[LLM Metrics]` log line for monitoring (Decision 2)
- `location_match` stays as user-facing data, not score component (Decision 3)
- `CandidateProfile.raw_perfil` marked with `# TODO: eliminar tras migrar todos los consumers`
