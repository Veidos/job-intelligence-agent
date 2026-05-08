"""
Orquestador del onboarding completo: extracción de CV + entrevista guiada.
Genera PERFIL.md (única fuente de verdad del candidato).
"""

import logging
import sys
from pathlib import Path

from src.onboarding.cv_extractor import extract_cv_data
from src.onboarding.interviewer import run_interview

log = logging.getLogger(__name__)


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

    # Skills técnicas con nivel
    lines += ["## Skills técnicas", ""]
    raw_skills = profile.get("skills_technical", [])
    if raw_skills and isinstance(raw_skills[0], dict):
        for skill in raw_skills:
            name = skill.get("name", "unknown")
            level = skill.get("level", "básico")
            evidence = skill.get("evidence", "sin evidencia")
            lines += [f"- **{name} ({level})**: {evidence}"]
    else:
        for skill in raw_skills:
            lines += [f"- {skill}"]
    lines += [""]

    # Gap de empleo
    gap_years = profile.get("employment_gap_years")
    if gap_years is not None:
        lines += ["## Gap de empleo", ""]
        lines += [f"- **Años:** {gap_years}"]

        # Usar el último trabajo real calculado (no el primero de la lista que puede ser académico)
        last_role = profile.get("_last_job_role")
        if last_role:
            # Buscar la compañía y duración de ese trabajo específico
            experience = profile.get("experience", [])
            for exp in experience:
                if exp.get("role") == last_role:
                    last_company = exp.get("company", "desconocida")
                    duration = exp.get("duration", "")
                    lines += [
                        f"- **Último trabajo:** {last_role} @ {last_company} ({duration})"
                    ]
                    break
            if not any("Último trabajo" in line for line in lines):
                lines += [f"- **Último trabajo:** {last_role}"]

        # Motivo del gap (si se sabe)
        personal_concerns = profile.get("personal_concerns", "")
        if personal_concerns and "gap" in personal_concerns.lower():
            lines += [f"- **Nota:** {personal_concerns}"]
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
