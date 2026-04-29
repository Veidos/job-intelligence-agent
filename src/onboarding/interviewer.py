"""
Entrevista guiada por gemma4 para completar el perfil del candidato.
Usa input() para preguntas secuenciales y gemma4 para procesar respuestas.
"""

import logging
from typing import Any

from src.utils.ollama_client import MODEL_HR, ollama_call

log = logging.getLogger(__name__)


def run_interview(cv_data: dict) -> dict[str, Any]:
    """
    Ejecuta entrevista guiada y devuelve campos faltantes del perfil.
    Args:
        cv_data: datos extraidos del CV por cv_extractor.py
    Returns:
        dict con campos listos para candidate_profile
    """
    print("\n=== Entrevista de perfil laboral ===\n")

    result: dict[str, Any] = {}

    # 1. Salario mínimo viable
    print("1. ¿Cuál es tu expectativa salarial mínima viable?")
    print("   (No la ideal, sino la mínima para decir sí)")
    salary_raw = input("   > ").strip()

    salary_prompt = f"""Eres un asesor laboral. El candidato responde así a su salario mínimo viable (bruto/año, euros):
"{salary_raw}"

Tu tarea:
1) Inferir un salario mínimo viable realista en euros como número (float).
2) Añadir una nota breve sobre margen de negociación.

Devuelve SOLO JSON válido con este esquema:
{{
  "salary_min_viable": float|null,
  "salary_notes": string
}}"""
    salary_info = ollama_call(MODEL_HR, salary_prompt, expect_json=True)
    result["salary_min_viable"] = salary_info.get("salary_min_viable")
    result["salary_notes"] = salary_info.get("salary_notes", "")

    # 2. Mudanza y condiciones
    print("\n2. ¿Disponibilidad real de mudanza y condiciones?")
    print("   (ej: dispuesto si pagan reubicación, solo remoto, etc.)")
    relocation_raw = input("   > ").strip()

    # 3. Modalidad de trabajo
    print("\n3. ¿Preferencia de modalidad de trabajo?")
    print("   (remoto / híbrido / presencial / sin preferencia)")
    result["work_mode_preference"] = input("   > ").strip().lower()

    # 4. Personal concerns
    print("\n4. ¿Hay algo sobre tu situación actual que quieras que el sistema")
    print("   tenga en cuenta al evaluar las ofertas? (responde libremente)")
    result["personal_concerns"] = input("   > ").strip()

    # 5. Sectores/empresas preferidas/evitar
    print("\n5. ¿Sectores o tipos de empresa que prefieras o quieras evitar?")
    print("   (menciona ambos libremente)")
    env_raw = input("   > ").strip()

    # Procesar respuestas con gemma4
    print("\n[Procesando respuestas con gemma4...]")

    reloc_prompt = f"""El candidato respondió: "{relocation_raw}"
Su ubicación actual según CV: {cv_data.get("location_current", "desconocida")}

Devuelve UNICAMENTE JSON válido con este esquema:
{{"location_preference": string, "relocation_conditions": string}}"""
    reloc = ollama_call(MODEL_HR, reloc_prompt, expect_json=True)
    result["location_preference"] = reloc.get("location_preference", "")
    result["relocation_conditions"] = reloc.get("relocation_conditions", relocation_raw)

    env_prompt = f"""El candidato respondió: "{env_raw}"

Devuelve UNICAMENTE JSON válido con este esquema:
{{"environment_prefer_keywords": [], "environment_avoid_keywords": []}}"""
    env = ollama_call(MODEL_HR, env_prompt, expect_json=True)
    result["environment_prefer_keywords"] = env.get("environment_prefer_keywords", [])
    result["environment_avoid_keywords"] = env.get("environment_avoid_keywords", [])

    print("[Listo]\n")
    return result
