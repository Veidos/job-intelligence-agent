"""
Extrae datos estructurados del CV usando gemma4:e4b.
Incluye skills con nivel y employment_gap_years.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.utils.ollama_client import MODEL_HR, ollama_call

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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
    """Construye el prompt para extraer datos completos del CV."""
    return f"""Eres un extractor de datos estructurados de CVs. Analiza el texto y responde UNICAMENTE con JSON válido.

CAMPOS A EXTRAER:
1. full_name: string (nombre completo)
2. location_current: string (ciudad/provincia actual)
3. skills_technical: lista de objetos {{"name": "skill", "level": "basico|intermedio|avanzado", "evidence": "frase justificativa"}}
   REGLAS DE NIVEL:
   - Si la skill se usó en EXPERIENCIA LABORAL REAL → nivel: avanzado
   - Si la skill se usó en PROYECTOS REALES/freelance → nivel: intermedio
   - Si la skill solo viene de FORMACIÓN/bootcamp/proyectos académicos → nivel: básico
   - NUNCA inferir nivel mayor al evidence disponible

4. employment_gap_years: número (años de gap laboral)
   CÁLCULO: Buscar última fecha de experiencia laboral real → calcular hasta fecha actual
   - Si hay experiencia continua → 0
   - Si hay gap desde último trabajo → restar años (ej: 2022 a 2026 = 3.5)

5. education: lista de objetos {{"degree": string, "institution": string, "year": int|null}}
6. experience: lista de objetos {{"role": string, "company": string, "duration": string, "description": string}}
7. languages: lista de strings
8. projects: lista de objetos {{"name": string, "description": string}}

Si falta un campo usa null o []. No incluyas texto adicional.

TEXTO DEL CV:
{cv_text[:12000]}"""


def parse_experience_dates(experience: list[dict]) -> tuple[str | None, float | None]:
    """
    Infiere el gap de empleo desde las experiencias.
    Returns: (ultimo_trabajo_fecha, gap_years)
    """
    now = datetime.now()
    last_job_date = None

    for exp in experience:
        duration = exp.get("duration", "")
        if not duration:
            continue
        # Buscar patrones como "2020 - 2022", "Ene 2020 - Sep 2022", "2022"
        import re

        years = re.findall(r"\b(20\d{2})\b", duration)
        if years:
            try:
                year = int(max(years))
                if last_job_date is None or year > last_job_date:
                    last_job_date = year
            except ValueError:
                continue

    if last_job_date:
        gap = (now.year - last_job_date) + (now.month / 12)
        return f"{last_job_date}", round(gap, 1)

    return None, None


def extract_cv_data(cv_path: str | Path) -> dict[str, Any]:
    """
    Extrae datos estructurados del CV via gemma4:e4b.

    Returns:
        Diccionario con full_name, location_current, skills_technical,
        education, experience, languages, projects, employment_gap_years.
    """
    log.info("Extrayendo texto de %s", cv_path)
    cv_text = extract_text_from_pdf(cv_path)
    if not cv_text.strip():
        raise ValueError("No se pudo extraer texto del PDF")

    log.info("Llamando a %s para extracción", MODEL_HR)
    prompt = build_extraction_prompt(cv_text)
    result = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
    )

    if not isinstance(result, dict):
        log.warning("gemma4 no devolvió dict, creando estructura vacía")
        result = {}

    # Calcular employment_gap_years si no lo devolvió el modelo
    if result.get("employment_gap_years") is None:
        experience = result.get("experience", [])
        if experience:
            _, gap = parse_experience_dates(experience)
            if gap:
                result["employment_gap_years"] = gap

    return result


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
    except Exception:
        log.exception("Error extrayendo CV")
        sys.exit(1)


if __name__ == "__main__":
    main()
