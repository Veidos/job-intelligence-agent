"""JSON Schemas para grammar constraints vía Ollama `format` (ADR-024).

Diseño validado con sondas empíricas (2026-08-25):
- Con `format`, gemma4:e4b emite JSON crudo válido (sin fences) a igual
  velocidad (~23 tok/s) — cero penalización observada.
- La traza `think` de gemma4 ya era intermitente antes (PLANS.md); el
  razonamiento exigible vive en los CAMPOS del schema (reasoning/verdict),
  preservando la regla "gemma4 nunca scores numéricos sin razonamiento".

Principio permisivo-en-contenido / estricto-en-estructura:
- Tipos, enums y campos requeridos: estrictos
- Strings libres; arrays SIN minItems (evitar relleno artificial)
- Campos anulables: ["T", "null"] — elimina de raíz el bug del literal
  "null" como string (ADR-014)

Alcance escalonado: solo evaluate.py en esta fase. Clasificador, empresas,
onboarding quedan para medición posterior.
"""

from __future__ import annotations

SKILL_PRESENT_ITEM = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "present": {"type": "boolean"},
        "candidate_level": {
            "type": ["string", "null"],
            "enum": ["basico", "intermedio", "avanzado", None],
        },
    },
    "required": ["name", "present"],
}

TECHNICAL_SCHEMA = {
    "type": "object",
    "properties": {
        "skills_present": {"type": "array", "items": SKILL_PRESENT_ITEM},
        "reasoning": {"type": "string"},
    },
    "required": ["skills_present", "reasoning"],
}

HR_SCHEMA = {
    "type": "object",
    "properties": {
        "context_fit": {"type": "number"},
        "environment_compatibility": {
            "type": "string",
            "enum": ["alta", "media", "baja"],
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "hr_concerns": {"type": "array", "items": {"type": "string"}},
        "interview_prep": {"type": "array", "items": {"type": "string"}},
        "gap_severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "apply_signal": {"type": "string", "enum": ["yes", "no", "maybe"]},
        "verdict": {"type": "string"},
    },
    "required": [
        "context_fit",
        "environment_compatibility",
        "apply_signal",
        "gap_severity",
        "verdict",
    ],
}

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "relevance_validation": {"type": "string", "enum": ["confirmed", "corrected"]},
        "relevance_corrected": {
            "type": ["string", "null"],
            "enum": ["core", "adjacent", "stretch", "temporal", None],
        },
        "relevance_reasoning": {"type": "string"},
        "apply_block": {
            "type": ["string", "null"],
            "enum": ["requisito_imposible", "practicas", "otro", None],
        },
        "apply_block_reason": {"type": ["string", "null"]},
        "apply_recommendation": {"type": "string", "enum": ["yes", "maybe", "no"]},
        "verdict": {"type": "string"},
    },
    "required": [
        "relevance_validation",
        "relevance_reasoning",
        "apply_recommendation",
        "verdict",
    ],
}
