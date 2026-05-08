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

    # 1. Modalidad de trabajo
    print("1. ¿Preferencia de modalidad de trabajo?")
    print("   (remoto / híbrido / presencial / sin preferencia)")
    result["work_mode_preference"] = input("   > ").strip().lower()

    # 2. Mudanza y condiciones
    print("\n2. ¿Disponibilidad real de mudanza y condiciones?")
    print("   (ej: dispuesto si pagan reubicación, solo remoto, etc.)")
    relocation_raw = input("   > ").strip()

    # 3. Personal concerns (nuevo formato constructivo)
    print("\n3. Contexto personal para encontrar el trabajo adecuado")
    print(
        "   [INFO] Esta información ayuda al sistema a encontrar ofertas\n"
        "          que se ajusten mejor a tu situación."
    )

    # Subpregunta 3a: Condiciones que afectan al trabajo
    print("   3a. ¿Tienes alguna condición (TDAH, autism, limitaciones físicas, etc.)")
    print("       que afecte cómo trabajas? (opcional, responde libremente)")
    condition_raw = input("      > ").strip()

    # Subpregunta 3b: Entorno de trabajo
    print("\n   3b. ¿Qué tipo de entorno te hace funcionar mejor?")
    print(
        "       (ej: necesito silencio, soy introvertido, necesito movimiento, flexible)"
    )
    environment_raw = input("      > ").strip()

    # Subpregunta 3c: Inseguridades
    print("\n   3c. ¿Hay algo que te dé inseguridad sobre buscar trabajo?")
    print("       (ej: 'tengo 3 años gap', 'estoy desactualizado', 'tengo edad')")
    insecurity_raw = input("      > ").strip()

    # Unir todo en personal_concerns
    personal_parts = []
    if condition_raw:
        personal_parts.append(f"Condición: {condition_raw}")
    if environment_raw:
        personal_parts.append(f"Entorno: {environment_raw}")
    if insecurity_raw:
        personal_parts.append(f"Inseguridad: {insecurity_raw}")

    result["personal_concerns"] = (
        " | ".join(personal_parts) if personal_parts else "Sin información adicional"
    )

    # 4. Sectores/empresas preferidas/evitar
    print("\n4. ¿Sectores o tipos de empresa que prefieras o quieras evitar?")
    print("   (menciona ambos libremente)")
    env_raw = input("   > ").strip()

    # Procesar respuestas
    print("\n[Procesando tus respuestas...]")

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
