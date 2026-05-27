"""
Generador de keywords de búsqueda a partir del perfil del candidato.

Flujo:
    1. Lee PERFIL.md
    2. Llama al LLM (gemma4:e4b via Ollama) para extraer títulos de puesto
    3. Escribe role_hierarchy en search_config (UPDATE si existe, INSERT si no)

Solo necesita ejecutarse UNA VEZ (o cuando el perfil cambie significativamente).
El pipeline diario consume role_hierarchy tal cual, sin tocar este módulo.

Uso:
    python -m src.onboarding.keyword_generator
    python -m src.onboarding.keyword_generator --dry-run   # imprime sin guardar
"""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.db.init_db import get_connection
from src.utils.ollama_client import ollama_call

log = logging.getLogger(__name__)

PERFIL_PATH = Path(__file__).resolve().parent.parent.parent / "PERFIL.md"
MAX_KEYWORDS = 8

SYSTEM_PROMPT = """Eres un recruiter senior con 10 años de experiencia publicando
ofertas en InfoJobs España. Conoces exactamente qué títulos de puesto usan las
empresas españolas en sus búsquedas reales."""

USER_PROMPT_TEMPLATE = """Analiza este perfil profesional y genera los títulos de
puesto que una empresa española publicaría en InfoJobs para contratar a este candidato.
PERFIL:
{perfil}
Reglas estrictas:
- Exactamente {max_kw} títulos únicos, sin variantes del mismo rol
- Sin indicadores de seniority (nada de Junior, Senior, Trainee, Mid)
- Incluye versiones en inglés Y en español de los roles principales, son búsquedas distintas en InfoJobs
- Cubre áreas distintas del perfil — no repitas el mismo concepto en el mismo idioma
- Ordena de MÁS a MENOS volumen de ofertas reales en InfoJobs España
- Usa el nombre base del rol, sin adjetivos ni especializaciones innecesarias
- Usa únicamente títulos que existan realmente en InfoJobs España — no inventes traducciones literales
Devuelve SOLO este JSON, sin texto extra, sin markdown:
{{"keywords": ["título 1", "título 2", "título 3"]}}"""


def load_perfil(path: Path = PERFIL_PATH) -> str:
    if not path.exists():
        raise FileNotFoundError(f"PERFIL.md no encontrado en {path}")
    return path.read_text(encoding="utf-8")


def generate_keywords(perfil_text: str) -> list[str]:
    """Llama al LLM y devuelve lista de keywords ordenada por relevancia."""
    prompt = USER_PROMPT_TEMPLATE.format(
        perfil=perfil_text[:4000],
        max_kw=MAX_KEYWORDS,
    )

    try:
        result = ollama_call(
            model="gemma4:e4b",
            prompt=prompt,
            expect_json=True,
            temperature=0.1,
            think=True,
        )
    except Exception as e:
        log.error("LLM falló generando keywords: %s", e)
        return []

    if not isinstance(result, dict):
        log.error("LLM devolvió tipo inesperado: %s", type(result))
        return []

    keywords = result.get("keywords", [])
    if not isinstance(keywords, list):
        log.error("Campo 'keywords' no es lista: %s", keywords)
        return []

    clean = [str(k).strip() for k in keywords if k and str(k).strip()][:MAX_KEYWORDS]
    log.info("Keywords generadas (%d): %s", len(clean), clean)
    return clean


def save_to_search_config(keywords: list[str], conn=None) -> bool:
    """
    Persiste role_hierarchy en search_config.
    - Si ya existe un registro → UPDATE (preserva geo_hierarchy, active_*)
    - Si no existe → INSERT con valores mínimos
    """
    if not keywords:
        log.error("Lista de keywords vacía, no se guarda nada")
        return False

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        role_hierarchy_json = json.dumps(keywords, ensure_ascii=False)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM search_config ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            cursor.execute(
                """
                UPDATE search_config
                SET role_hierarchy = ?,
                    last_updated   = datetime('now')
                WHERE id = ?
                """,
                (role_hierarchy_json, row[0]),
            )
            log.info(
                "search_config id=%d actualizado con %d keywords", row[0], len(keywords)
            )
        else:
            cursor.execute(
                """
                INSERT INTO search_config (role_hierarchy, geo_hierarchy, active_geo_level, active_role_level)
                VALUES (?, ?, ?, ?)
                """,
                (role_hierarchy_json, json.dumps(["nacional"]), 0, 0),
            )
            log.info("search_config creado con %d keywords", len(keywords))

        conn.commit()
        return True

    except Exception as e:
        log.error("Error guardando en search_config: %s", e)
        return False
    finally:
        if own_conn:
            conn.close()


def run(dry_run: bool = False) -> list[str]:
    perfil = load_perfil()
    log.info("PERFIL.md cargado (%d chars)", len(perfil))

    keywords = generate_keywords(perfil)

    if not keywords:
        log.error("No se generaron keywords. Revisa la conexión con Ollama.")
        return []

    print("\n── Keywords generadas ──────────────────────────────")
    for i, kw in enumerate(keywords, 1):
        print(f"  {i}. {kw}")
    print("────────────────────────────────────────────────────\n")

    if dry_run:
        print("[dry-run] No se guardó en DB.")
        return keywords

    saved = save_to_search_config(keywords)
    if saved:
        print(f"✓ {len(keywords)} keywords guardadas en search_config.role_hierarchy")
    else:
        print("✗ Error al guardar. Revisa los logs.")

    return keywords


def manage_keywords() -> None:
    """Muestra las keywords actuales y permite eliminar por número."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, role_hierarchy FROM search_config ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            print("No hay keywords guardadas en search_config.")
            return
        config_id, role_hierarchy_json = row
        keywords = json.loads(role_hierarchy_json)
        print("\n── Keywords actuales ───────────────────────────────")
        for i, kw in enumerate(keywords, 1):
            print(f"  {i}. {kw}")
        print("────────────────────────────────────────────────────")
        raw = input("\nNúmeros a conservar (ej: 1 2 4 6 8) o Enter para mantener todas: ").strip()
        if not raw:
            print("Sin cambios.")
            return
        keep = set()
        for token in raw.split():
            if token.isdigit() and 1 <= int(token) <= len(keywords):
                keep.add(int(token) - 1)
        if not keep:
            print("Ningún número válido. Sin cambios.")
            return
        updated = [kw for i, kw in enumerate(keywords) if i in keep]
        cursor.execute(
            "UPDATE search_config SET role_hierarchy = ?, last_updated = datetime('now') WHERE id = ?",
            (json.dumps(updated, ensure_ascii=False), config_id),
        )
        conn.commit()
        print(f"\n✓ Conservadas {len(keep)} keywords. Quedan {len(updated)}:")
        for i, kw in enumerate(updated, 1):
            print(f"  {i}. {kw}")
        raw_add = input("\nKeywords a añadir (separadas por comas si son varias, o una sola) o Enter para saltar: ").strip()
        if raw_add:
            nuevas = [kw.strip() for kw in raw_add.split(",") if kw.strip()]
            existing_lower = {k.lower() for k in updated}
            for kw in nuevas:
                if kw and kw.lower() not in existing_lower:
                    updated.append(kw)
                    existing_lower.add(kw.lower())
            cursor.execute(
                "UPDATE search_config SET role_hierarchy = ?, last_updated = datetime('now') WHERE id = ?",
                (json.dumps(updated, ensure_ascii=False), config_id),
            )
            conn.commit()
            print(f"\n✓ Añadidas {len(nuevas)} keywords. Total: {len(updated)}:")
            for i, kw in enumerate(updated, 1):
                print(f"  {i}. {kw}")
    finally:
        conn.close()


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    if "--manage" in sys.argv:
        manage_keywords()
    else:
        dry = "--dry-run" in sys.argv
        run(dry_run=dry)
