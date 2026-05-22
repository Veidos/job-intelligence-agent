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
    print("Responde con el detalle que consideres. Puedes dejar vacío si no aplica.\n")

    result: dict[str, Any] = {}

    # 1. Modalidad + mudanza (fusionado, abierto)
    print("1. ¿Modalidad de trabajo y disponibilidad de mudanza?")
    print(
        "   (ej: 'remoto total', 'híbrido en Sevilla', 'presencial si pagan reubicación')"
    )
    relocation_raw = input("   > ").strip()

    # 2. Salario mínimo viable (opcional)
    print("\n2. ¿Salario mínimo anual para considerar una oferta? (opcional)")
    print("   (ej: '30.000€', déjalo vacío si no quieres filtrar por salario)")
    salary_raw = input("   > ").strip()
    if salary_raw:
        # Extraer número del texto
        import re

        numbers = re.findall(r"\d+", salary_raw.replace(".", "").replace(",", ""))
        if numbers:
            result["salary_min_viable"] = int(numbers[0])
            result["salary_notes"] = salary_raw

    # 3. Contexto personal (abierto con expectativas claras)
    print("\n3. Contexto personal relevante para tu búsqueda de trabajo")
    print("   Puedes incluir (si aplica):")
    print("   - Condiciones que afecten cómo trabajas (horarios, concentración, etc.)")
    print("   - Tipo de entorno donde rindes mejor (silencio, equipo, autonomía, etc.)")
    print("   - Cualquier otra cosa que quieras que el sistema considere")
    print("   (déjalo vacío si no aplica)")
    condition_raw = input("   > ").strip()
    environment_raw = input("   Entorno preferido (opcional): ").strip()

    personal_parts = []
    if condition_raw:
        personal_parts.append(f"Condición: {condition_raw}")
    if environment_raw:
        personal_parts.append(f"Entorno: {environment_raw}")

    result["personal_concerns"] = (
        " | ".join(personal_parts) if personal_parts else "Sin información adicional"
    )

    # 4. Motivación profesional (sustituye inseguridades — enfoque positivo)
    print("\n4. ¿Qué buscas en tu próximo rol profesional?")
    print(
        "   (ej: 'aprender ML en producción', 'consolidar análisis de datos',"
        " 'cambiar a un sector con impacto social')"
    )
    motivation_raw = input("   > ").strip()
    if motivation_raw:
        if result["personal_concerns"] == "Sin información adicional":
            result["personal_concerns"] = f"Motivación: {motivation_raw}"
        else:
            result["personal_concerns"] += f" | Motivación: {motivation_raw}"

    # 5. Sectores preferidos / a evitar
    print("\n5. ¿Hay sectores o tipos de empresa que te atraigan especialmente?")
    print("   ¿Y alguno que prefieras evitar?")
    print(
        "   (ej: 'me gusta tecnología y energía renovable, evitar banca tradicional')"
    )
    env_raw = input("   > ").strip()

    # Procesar respuestas con gemma4
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
