"""
Extrae datos estructurados del CV usando qwen2.5-coder:7b.
Popula candidate_skills desde el perfil usando gemma4.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import sqlite3

from pypdf import PdfReader

from src.utils.ollama_client import MODEL_HR, MODEL_TECHNICAL, ollama_call

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "jobs.db"


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extrae todo el texto de un archivo PDF."""
    reader = PdfReader(str(pdf_path))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def build_extraction_prompt(cv_text: str) -> str:
    """Construye el prompt para qwen2.5-coder:7b."""
    return f"""Eres un extractor de datos estructurados de CVs. Analiza el texto y responde UNICAMENTE con JSON valido.

Campos a extraer:
- full_name: string
- location_current: string (ciudad/provincia actual)
- skills_technical: lista de strings (habilidades tecnicas con nivel si aparece)
- education: lista de objetos {{"degree": string, "institution": string, "year": int|null}}
- experience: lista de objetos {{"role": string, "company": string, "duration": string, "description": string}}
- languages: lista de strings
- projects: lista de objetos {{"name": string, "description": string}}

Si falta un campo usa null o []. No incluyas texto adicional.

TEXTO DEL CV:
{cv_text[:12000]}
"""


def populate_candidate_skills(profile_text: str) -> None:
    """
    Extrae skills del perfil via gemma4 y popula candidate_skills.

    Args:
        profile_text: Texto completo del PERFIL.md
    """
    prompt = f"""Lee este perfil profesional y extrae TODAS las skills tecnicas mencionadas.
Para cada skill, infiere el nivel basandote unicamente en lo que aparece
en el perfil: proyectos, experiencia laboral, formacion.

Si no hay evidencia de nivel, usa 'basico'.
Niveles: basico | intermedio | avanzado | experto

Responde SOLO con JSON valido sin texto adicional:
{{
  "skills": [
    {{
      "name": "nombre exacto de la skill",
      "level": "nivel inferido",
      "evidence": "frase o contexto del perfil que justifica este nivel"
    }}
  ]
}}

PERFIL:
{profile_text}"""

    log.info("Llamando a %s para extraccion de skills", MODEL_HR)
    response = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
    )

    skills_data = response.get("skills", [])
    if not skills_data:
        log.warning("No se extrajeron skills del perfil")
        return

    log.info("Skills extraidas: %d", len(skills_data))

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM candidate_skills WHERE source = 'PERFIL.md'")

        for skill in skills_data:
            name = skill.get("name", "").strip()
            level = skill.get("level", "basico").strip()
            evidence = skill.get("evidence", "").strip()

            if not name:
                continue

            conn.execute(
                "INSERT OR IGNORE INTO skills (name) VALUES (?)",
                (name,),
            )

            conn.execute(
                """INSERT INTO candidate_skills (skill_id, level_current, evidence, source)
                   SELECT id, ?, ?, 'PERFIL.md' FROM skills WHERE name = ?
                   ON CONFLICT(skill_id) DO UPDATE SET
                     level_current = excluded.level_current,
                     evidence = excluded.evidence,
                     updated_at = datetime('now')""",
                (level, evidence, name),
            )

        conn.commit()

    print(f"Skills extraidas: {len(skills_data)} → candidate_skills actualizado")


def extract_cv_data(cv_path: str | Path) -> dict[str, Any]:
    """
    Extrae datos estructurados del CV via qwen2.5-coder:7b.

    Returns:
        Diccionario con full_name, location_current, skills_technical,
        education, experience, languages, projects.
    """
    log.info("Extrayendo texto de %s", cv_path)
    cv_text = extract_text_from_pdf(cv_path)
    if not cv_text.strip():
        raise ValueError("No se pudo extraer texto del PDF")

    log.info("Llamando a %s para extraccion", MODEL_TECHNICAL)
    prompt = build_extraction_prompt(cv_text)
    return ollama_call(
        model=MODEL_TECHNICAL,
        prompt=prompt,
        expect_json=True,
    )


def main() -> None:
    """Prueba manual del extractor."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cv_path = Path("assets/cv.pdf")
    if not cv_path.exists():
        log.error("No se encontro %s", cv_path)
        sys.exit(1)
    try:
        data = extract_cv_data(cv_path)
        print(json.dumps(data, indent=2, ensure_ascii=False))

        # Poblar candidate_skills desde PERFIL.md si existe
        perfil_path = PROJECT_ROOT / "PERFIL.md"
        if perfil_path.exists():
            profile_text = perfil_path.read_text(encoding="utf-8")
            populate_candidate_skills(profile_text)

            # Extraer y guardar skills con la nueva funcion
            with sqlite3.connect(DB_PATH) as conn:
                extract_and_save_candidate_skills(conn, profile_text)
        else:
            log.warning("PERFIL.md no encontrado, saltando populate_candidate_skills")
    except Exception:
        log.exception("Error extrayendo CV")
        sys.exit(1)


def extract_and_save_candidate_skills(conn, profile_text: str) -> int:
    """Lee PERFIL.md completo y usa gemma4 para poblar candidate_skills."""
    prompt = f"""Lee este perfil profesional y extrae TODAS las skills tecnicas.
Para cada skill infiere el nivel UNICAMENTE desde lo que aparece en el perfil
(proyectos, experiencia, formacion). Sin inventar nada.

Niveles validos: basico | intermedio | avanzado | experto

Responde SOLO con JSON valido, sin texto adicional:
{{
  "skills": [
    {{
      "name": "nombre de la skill",
      "level": "nivel inferido",
      "evidence": "frase del perfil que justifica el nivel"
    }}
  ]
}}

PERFIL:
{profile_text}"""

    response = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
    )

    skills = response.get("skills", [])

    # Limpiar solo skills de PERFIL.md
    conn.execute("DELETE FROM candidate_skills WHERE source = 'PERFIL.md'")

    count = 0
    for s in skills:
        name = s.get("name", "").strip()
        level = s.get("level", "basico")
        evidence = s.get("evidence", "")
        if not name:
            continue
        # Upsert en skills
        conn.execute("INSERT OR IGNORE INTO skills(name) VALUES (?)", (name,))
        skill_id = conn.execute(
            "SELECT id FROM skills WHERE name = ?", (name,)
        ).fetchone()[0]
        # Upsert en candidate_skills
        conn.execute(
            """
            INSERT INTO candidate_skills(skill_id, level_current, evidence, source)
            VALUES (?, ?, ?, 'PERFIL.md')
            ON CONFLICT(skill_id) DO UPDATE SET
                level_current = excluded.level_current,
                evidence = excluded.evidence,
                updated_at = datetime('now')
        """,
            (skill_id, level, evidence),
        )
        count += 1

    conn.commit()
    print(f"✅ Skills extraidas: {count} → candidate_skills actualizado")
    return count


if __name__ == "__main__":
    main()
