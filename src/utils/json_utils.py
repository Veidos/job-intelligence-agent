import json
import logging

log = logging.getLogger(__name__)


def _extract_json(text: str):
    """Extrae JSON de respuesta del modelo, manejando texto extra."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```" in text:
        for block in text.split("```"):
            cleaned = block.strip().lstrip("json").strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
    for sc, ec in [("{", "}"), ("[", "]")]:
        s, e = text.find(sc), text.rfind(ec)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"No se pudo extraer JSON de: {text[:200]}...")
