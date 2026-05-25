# ADR-005: Role Classifier — design decisions and evolution v1 → v6

**Date:** 2026-05-22
**Type:** `architecture`
**Status:** `active`
**Component:** `src/pipeline/role_classifier.py`
**Report module:** `scripts/reporte_v6.py`

---

## Context

The role classifier assigns each scraped offer a canonical `role_normalized` and a `relevance_flag` (`core / adjacent / stretch / temporal`) with its `gap_type` (`seniority / domain / tool / structural / none`) that measures the distance from the candidate to the role. It operates with **gemma4:e4b** via Ollama (single prompt, no history between offers).

Iterative development v1→v6 revealed three recurring problems:

1. **The model is optimistic by default.** Without an explicit decision structure, gemma4 classifies every offer as `core` (v1: 16/17 core).
2. **Coupled prompt changes produce regressions.** v4 introduced a parsing fix and a prompt restructure in the same change, causing a silent collapse to `core` that went unnoticed for a full workday.
3. **The LLM is not reliable for structural binary decisions.** `is_new_role` returned by gemma4 gave a false negative for `trade_compliance_specialist`, preventing its addition to the catalog.

---

## Decision

**Separate classifier reasoning into two independent axes (PHASE 1: role objective, PHASE 2: candidate fit) and delegate to the LLM exclusively the semantic judgment, while all verifiable deterministic decisions (new role detection, gap_type hierarchy, JSON field validation) live in Python code.**

The four design rules governing the classifier since v5/v6:

| Rule | Statement |
|------|-----------|
| **The model reasons, Python decides** | Detection of `is_new_role`, resolution of `gap_type`, JSON validation → code. The LLM only classifies semantically. |
| **Atomic prompt changes** | Never combine a parsing fix with a prompt restructure. One change = one variable. |
| **Axis separation** | PHASE 1 describes the position objectively; PHASE 2 evaluates the candidate. Mixing them contaminates both judgments. |
| **Traceability always** | `is_new_role` proved that non-persisted computed fields are lost. Since v6: if it is computed in the pipeline, it is saved in DB. |

---

## Discarded alternatives

- **Monolithic prompt without phases (v1).** Produces collapse to `core` due to model optimism. Discarded as unviable.
- **Delegating `is_new_role` to the LLM (v1–v5).** False negative in `trade_compliance_specialist`. Reliability of local models for structural binary decisions is lower than `O(n)` in Python. Discarded.
- **Delegating entire `gap_type` to the LLM (v1–v4).** Produces format errors (dicts instead of strings) and inconsistencies. Discarded; the hierarchy is resolved in `resolve_gap_type`.
- **Using a larger model (qwen2.5-coder:7b).** Tested and discarded during early development (MEMORIES.md:87): it did not reason well in broad context. gemma4:e4b is the only model in the pipeline.
- **Not persisting `is_new_role`.** Any computed field that is not saved in DB is lost when reprocessing. Discarded for violating traceability.

---

## Consequences

- **Classifier quality is bounded by gemma4:e4b.** Borderline roles (`data_scientist` vs `data_analyst`) and `structural` gap have accepted noise as a limitation of the local model. Improvable with a superior model.
- **The role catalog grows dynamically.** Each new detected `role_normalized` is added automatically. Requires periodic review to avoid spurious or duplicate roles.
- **The "if it is computed, it is saved" rule is binding.** Any new derived field in the pipeline must be added to the schema and persisted. `ensure_columns_exist` and `migrate.py` must be maintained.
- **The HTML generator must preserve order by `id` ASC.** Bug detected in v6 and fixed: the scripts use explicit `ORDER BY id`.
- **Next natural step:** improve the prompt to discriminate `structural` vs `stretch` reliably, and review whether `bi_analyst` deserves its own slot in the catalog.

---

## Annex A: Version history

| Version | Change | Distribution | Problem |
|---------|--------|-------------|----------|
| v1 | Baseline without decision structure | core:16 / adjacent:1 | Collapse due to model optimism |
| v2 | PHASE 1 + PHASE 2 separated | adjacent:8 / stretch:9 | gap_types as list of dicts (unhashable error) |
| v4 | Unhashable fix + prompt restructure | core:16 / stretch:1 | Regression from coupled change |
| v5 | v2 prompt restored + clean parsing fix | adjacent:8 / stretch:9 | Stable (13/17 correct in manual evaluation) |
| v6 | Deterministic `is_new_role` in Python + DB column | adjacent:8 / stretch:9 | Catalog grows to 18 roles; ORDER BY bug fixed |

## Annex B: Correctness evaluation v5/v6 (13/17)

| ID | Offer | Assigned flag | Expected flag | Correct |
|----|-------|--------------|---------------|:-------:|
| 226 | Looker Quest Global | stretch / seniority | adjacent / tool | ⚠️ |
| 227 | Izertis BD | stretch / seniority | stretch / seniority | ✅ |
| 228 | New Tandem | adjacent / domain | adjacent / tool | ⚠️ |
| 229 | NTT Junior PBI | stretch / seniority | adjacent / tool | ⚠️ |
| 230 | EY Internship | adjacent / domain | adjacent / domain | ✅ |
| 231–233, 235–242 | Others | — | — | ✅ |

## Annex C: Current catalog (18 roles)

`data_analyst`, `data_scientist`, `ml_engineer`, `bi_analyst`, `data_engineer`, `operations_analyst`, `quality_analyst`, `process_engineer`, `technical_support`, `temporal`, `real_estate_consultant`, `martech_consultant`, `erp_consultant`, `it_consultant`, `recruitment_specialist`, `b2b_sales_representative`, `market_research_analyst`, **`trade_compliance_specialist`** (new in v6).
