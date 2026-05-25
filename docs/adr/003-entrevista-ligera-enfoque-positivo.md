# 003 — Lightweight interview with positive focus

**Date:** 2026-05-22
**Type:** `operational`
**Status:** `active`

## Context
The original interview had 6 effective questions, including one about
job insecurities that generated unnecessary anxiety. The field
`salary_min_viable` existed in PERFIL.md but was never asked.
Additionally, `work_mode_preference` and `relocation_conditions` were
separate questions when they could be merged into a single open response.

## Decision
Redesign the interview to 5 questions, removing the negative question
and adding optional salary and professional motivation:

1. **Mode + relocation** (single open question, processed by gemma4)
2. **Minimum viable salary** (new, optional — empty = no filter)
3. **Personal context** (all in one input, with examples of what to include)
4. **Professional motivation** (positive focus, replaces insecurities)
5. **Preferred / avoid sectors** (processed by gemma4 into keywords)

The examples in each question are generic, not hardcoded to the candidate's
profile.

## Discarded alternatives
- **Keep the insecurity question:** counterproductive, generates
  negative self-diagnosis that contaminates personal_concerns.
- **Question 3 split into two inputs (conditions + environment):** confusing,
  the user does not know whether to repeat information or separate it.
- **Mandatory salary:** breaks the flow if no salary filtering is desired.

## Consequences
- `work_mode_preference`, `location_preference` and `relocation_conditions`
  are extracted from a single response via gemma4.
- `personal_concerns` is free text with no forced structure.
- Motivation is stored as part of `personal_concerns` so that
  gemma4 can use it as psychological context in evaluations.
- Examples must be kept generic when modifying the interview.
