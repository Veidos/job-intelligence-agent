"""
Limpieza y normalización de datos de ofertas de trabajo.
"""


def clean_text(text: str | None) -> str:
    """Limpia texto genérico: elimina exceso de espacios y saltos de línea."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def clean_description(raw: str | None) -> str:
    """Limpieza específica para descripciones de ofertas."""
    if not raw:
        return ""
    cleaned = raw.replace("\r", "").replace("\t", " ")
    # Eliminar saltos de línea múltiples
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    # Limpiar espacios finales por línea
    lines = [line.rstrip() for line in cleaned.split("\n")]
    return "\n".join(lines).strip()
