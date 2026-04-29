"""
Extrae datos estructurados del CV usando qwen2.5-coder:7b.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from src.utils.ollama_client import MODEL_TECHNICAL, ollama_call

log = logging.getLogger(__name__)


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
    except Exception:
        log.exception("Error extrayendo CV")
        sys.exit(1)


if __name__ == "__main__":
    main()
