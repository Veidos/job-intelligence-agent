"""
Orquesta el onboarding completo: extracción de CV + entrevista guiada.
Genera PERFIL.md en la raíz del proyecto sin tocar la base de datos.
"""

import logging
import sys
from pathlib import Path

from src.onboarding.cv_extractor import extract_cv_data
from src.onboarding.interviewer import run_interview

log = logging.getLogger(__name__)


def normalize_skills(skills: list) -> list[str]:
    """Normaliza la lista de skills técnicas a strings legibles."""
    normalized: list[str] = []
    for item in skills:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            for skill_name, level in item.items():
                if level is None:
                    normalized.append(skill_name)
                else:
                    normalized.append(f"{skill_name}: {level}")
    return normalized


def generate_perfil_md(profile: dict) -> str:
    """Genera el contenido de PERFIL.md desde el dict de perfil combinado."""
    lines: list[str] = ["# PERFIL DEL CANDIDATO", ""]

    # Datos base
    lines += ["## Datos base", ""]
    lines += [f"- **Nombre:** {profile.get('full_name', 'N/A')}"]
    lines += [f"- **Ubicación actual:** {profile.get('location_current', 'N/A')}"]
    salary = profile.get("salary_min_viable")
    if salary is not None:
        lines += [f"- **Salario mínimo viable:** {salary} €"]
        notes = profile.get("salary_notes", "")
        if notes:
            lines += [f"  - Notas: {notes}"]
    lines += [""]

    # Skills técnicas
    lines += ["## Skills técnicas", ""]
    raw_skills = profile.get("skills_technical", [])
    for skill in normalize_skills(raw_skills):
        lines += [f"- {skill}"]
    lines += [""]

    # Educación
    lines += ["## Educación", ""]
    for edu in profile.get("education", []):
        year = edu.get("year", "N/A")
        lines += [
            f"- **{edu.get('degree', 'N/A')}** — "
            f"{edu.get('institution', 'N/A')} ({year})"
        ]
    lines += [""]

    # Experiencia
    lines += ["## Experiencia", ""]
    for exp in profile.get("experience", []):
        lines += [f"### {exp.get('role', 'N/A')} @ {exp.get('company', 'N/A')}"]
        lines += [f"**Duración:** {exp.get('duration', 'N/A')}"]
        desc = exp.get("description", "")
        if desc:
            lines += [f"**Descripción:** {desc}"]
        lines += [""]

    # Idiomas
    lines += ["## Idiomas", ""]
    for lang in profile.get("languages", []):
        lines += [f"- {lang}"]
    lines += [""]

    # Proyectos
    lines += ["## Proyectos", ""]
    for proj in profile.get("projects", []):
        lines += [f"### {proj.get('name', 'N/A')}"]
        desc = proj.get("description", "")
        if desc:
            lines += [desc]
        lines += [""]

    # Preferencias laborales
    lines += ["## Preferencias laborales", ""]
    lines += [
        f"- **Modalidad preferida:** {profile.get('work_mode_preference', 'N/A')}"
    ]
    lines += [f"- **Ubicación preferida:** {profile.get('location_preference', 'N/A')}"]
    lines += [
        f"- **Condiciones de mudanza:** {profile.get('relocation_conditions', 'N/A')}"
    ]
    lines += [""]

    # Personal concerns (íntegro, sin resumir)
    lines += ["## Personal concerns", ""]
    lines += [profile.get("personal_concerns", "N/A")]
    lines += [""]

    # Entorno preferido / a evitar
    lines += ["## Entorno preferido / a evitar", ""]
    prefer = profile.get("environment_prefer_keywords", [])
    avoid = profile.get("environment_avoid_keywords", [])
    if prefer:
        lines += ["**Preferencias:**"] + [f"- {kw}" for kw in prefer]
    if avoid:
        lines += ["**Evitar:**"] + [f"- {kw}" for kw in avoid]
    lines += [""]

    return "\n".join(lines)


def main() -> None:
    """Ejecuta el onboarding completo y genera PERFIL.md."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log.info("Iniciando onboarding...")

    cv_path = Path("assets/cv.pdf")
    if not cv_path.exists():
        log.error("No se encontro %s", cv_path)
        sys.exit(1)

    log.info("Extrayendo datos del CV...")
    cv_data: dict = extract_cv_data(cv_path)

    log.info("Iniciando entrevista guiada...")
    interview_data: dict = run_interview(cv_data)

    # Combinar ambos dicts (interview_data sobrescribe si hay solapamiento)
    profile: dict = {**cv_data, **interview_data}

    log.info("Generando PERFIL.md...")
    md_content: str = generate_perfil_md(profile)

    output_path = Path("PERFIL.md")
    output_path.write_text(md_content, encoding="utf-8")
    log.info("PERFIL.md generado en %s", output_path.resolve())

    print("\n=== PERFIL.md generado ===\n")
    print("Revisa el archivo y edítalo manualmente si es necesario.")
    print("El sistema lee PERFIL.md en cada sesión de evaluación.\n")


if __name__ == "__main__":
    main()
