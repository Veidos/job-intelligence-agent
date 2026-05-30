"""Role classifier for job offers.

Classifies offers into roles from a catalog and assigns relevance flags.
Uses gemma4 for classification.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import argparse
from pathlib import Path
from typing import Any

from src.utils.ollama_client import MODEL_TECHNICAL, ollama_call

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"

INITIAL_ROLES = [
    "data_analyst",
    "data_scientist",
    "ml_engineer",
    "bi_analyst",
    "data_engineer",
    "operations_analyst",
    "quality_analyst",
    "process_engineer",
    "technical_support",
    "temporal",
]

GAP_HIERARCHY = ["estructural", "seniority", "dominio", "herramienta", "none"]

GAP_TO_FLAG: dict[str, str] = {
    "none": "core",
    "herramienta": "adjacent",
    "dominio": "adjacent",
    "seniority": "stretch",
    "estructural": "temporal",
}


def resolve_gap_type(gaps: list[str]) -> str:
    """Apply hierarchy with heuristic: seniority alone beats all except estructural,
    but if seniority only coexists with herramienta (no dominio/estructural),
    herramienta wins (seniority was inflated by the model seeing a junior profile)."""
    if not gaps or not isinstance(gaps, list):
        return "none"
    seen = set(g for g in gaps if isinstance(g, str))
    if not seen:
        return "none"
    if "estructural" in seen:
        return "estructural"

    if "seniority" in seen and "dominio" not in seen and "estructural" not in seen:
        return "herramienta" if "herramienta" in seen else "seniority"

    for level in GAP_HIERARCHY:
        if level in seen:
            return level
    return "none"


def ensure_columns_exist(conn: sqlite3.Connection) -> None:
    """Ensure role_catalog exists in search_config and role_normalized in offers."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(search_config)")
    sc_columns = {row[1] for row in cursor.fetchall()}
    if "role_catalog" not in sc_columns:
        logger.info("Adding role_catalog column to search_config")
        cursor.execute("ALTER TABLE search_config ADD COLUMN role_catalog TEXT")
        conn.commit()

    cursor.execute("PRAGMA table_info(offers)")
    offers_columns = {row[1] for row in cursor.fetchall()}
    if "role_normalized" not in offers_columns:
        logger.info("Adding role_normalized column to offers")
        cursor.execute("ALTER TABLE offers ADD COLUMN role_normalized TEXT")
        conn.commit()

    if "gap_type" not in offers_columns:
        logger.info("Adding gap_type column to offers")
        cursor.execute("ALTER TABLE offers ADD COLUMN gap_type TEXT")
        conn.commit()

    if "role_reasoning" not in offers_columns:
        logger.info("Adding role_reasoning column to offers")
        cursor.execute("ALTER TABLE offers ADD COLUMN role_reasoning TEXT")
        conn.commit()

    if "is_new_role" not in offers_columns:
        logger.info("Adding is_new_role column to offers")
        cursor.execute("ALTER TABLE offers ADD COLUMN is_new_role INTEGER DEFAULT 0")
        conn.commit()


def get_role_catalog(conn: sqlite3.Connection) -> list[str]:
    """Get role catalog from search_config, or create initial one."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role_catalog FROM search_config ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()

    if row is None:
        logger.info("No search_config found, creating with initial roles")
        initial_catalog = json.dumps(INITIAL_ROLES)
        cursor.execute(
            "INSERT INTO search_config (role_catalog, generated_at) VALUES (?, datetime('now'))",
            (initial_catalog,),
        )
        conn.commit()
        return INITIAL_ROLES

    role_catalog_json = row[1]
    if role_catalog_json is None:
        logger.info("role_catalog is NULL, setting initial roles")
        initial_catalog = json.dumps(INITIAL_ROLES)
        cursor.execute(
            "UPDATE search_config SET role_catalog = ? WHERE id = ?",
            (initial_catalog, row[0]),
        )
        conn.commit()
        return INITIAL_ROLES

    try:
        catalog = json.loads(role_catalog_json)
        logger.info(f"Loaded role catalog with {len(catalog)} roles")
        return catalog
    except json.JSONDecodeError:
        logger.warning("Failed to parse role_catalog JSON, resetting to initial")
        initial_catalog = json.dumps(INITIAL_ROLES)
        cursor.execute(
            "UPDATE search_config SET role_catalog = ? WHERE id = ?",
            (initial_catalog, row[0]),
        )
        conn.commit()
        return INITIAL_ROLES


def update_role_catalog(conn: sqlite3.Connection, catalog: list[str]) -> None:
    """Update role_catalog in search_config."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM search_config ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row is None:
        logger.warning("No search_config row found, cannot update role_catalog")
        return
    catalog_json = json.dumps(catalog)
    cursor.execute(
        "UPDATE search_config SET role_catalog = ?, last_updated = datetime('now') WHERE id = ?",
        (catalog_json, row[0]),
    )
    conn.commit()
    logger.info(f"Updated role catalog with {len(catalog)} roles")


FORBIDDEN_IN_ROLE_REASONING = [
    "candidato",
    "del candidato",
    "del perfil",
    "perfil del",
    "Miguel",
    "Bohórquez",
    "gap de empleo",
    "bootcamp",
    "años sin",
    "recién graduado",
    "sin experiencia",
]


def _build_prompt(
    title: str,
    description: str,
    skills: str,
    catalog: list[str],
    perfil_content: str,
) -> str:
    catalog_str = ", ".join(catalog)
    return f"""Eres un clasificador de ofertas. Responde en dos fases.

FASE 1 — analiza el puesto. Ignora completamente al candidato.
Catálogo disponible: {catalog_str}

Oferta:
- Título: {title}
- Skills requeridas: {skills}
- Descripción: {description}

Determina:
- función dominante: análisis_reporting | ingeniería_datos | modelado_ml | consultoría_procesos | gobierno_dato | soporte_técnico | compliance | otra
- requisitos: separa obligatorios de valorables según la descripción
- seniority del puesto: ejecutar_tareas | definir_procesos | liderar_equipos
- coherencia título vs descripción: coincide | discrepa
- role_normalized: elige del catálogo o propón nuevo en snake_case
- role_reasoning: una sola frase describiendo el puesto. No menciones al candidato.

FASE 2 — evalúa el fit con el perfil.
Perfil:
{perfil_content}

Para cada gap, pregúntate:
- ¿La oferta pide una herramienta concreta (Power BI, Looker, DAX, SAP...)
  que NO aparece en el perfil? → herramienta
- ¿La oferta requiere experiencia en un sector (automoción, finanzas, 
  defensa, legal...) que el candidato no tiene? → dominio  
- ¿La oferta exige experiencia práctica acreditable, años de experiencia
  o nivel de responsabilidad que el candidato no demuestra? → seniority
- ¿La oferta exige algo imposible para el candidato (titulación 
  obligatoria, certificación específica, discapacidad)? → estructural
- ¿El candidato cubre todo lo requerido? → none

Devuelve TODOS los gaps que apliquen (puede ser más de uno).
Si hay algún gap, gap_types NO puede ser [].

Responde SOLO este JSON:
{{"role_normalized":"...","role_reasoning":"...","gap_types":[],"is_new_role":false,"reasoning":"..."}}"""


def classify_offer(
    offer: dict[str, Any],
    catalog: list[str],
    perfil_content: str,
    model: str = MODEL_TECHNICAL,
) -> dict[str, Any] | None:
    """Classify an offer using gemma4."""
    title = offer.get("title", "")
    description = offer.get("description_clean") or offer.get("description_raw") or ""
    if description:
        description = description[:2000]
    skills_raw = offer.get("skills_required") or ""
    if skills_raw.startswith("["):
        try:
            skills_list = json.loads(skills_raw)
            skills_str = ", ".join(skills_list)[:800]
        except json.JSONDecodeError:
            skills_str = skills_raw[:800]
    else:
        skills_str = skills_raw[:800]

    prompt = _build_prompt(title, description, skills_str, catalog, perfil_content)
    try:
        result = ollama_call(
            model=model,
            prompt=prompt,
            expect_json=True,
            think=True,
        )
        if result is None:
            logger.warning(f"gemma4 returned None for offer {offer.get('id')}")
            return None
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse gemma4 response for offer {offer.get('id')}"
                )
                return None
        required_fields = [
            "role_normalized",
            "role_reasoning",
            "gap_types",
            "is_new_role",
            "reasoning",
        ]
        for field in required_fields:
            if field not in result:
                logger.warning(
                    f"Missing field {field} in response for offer {offer.get('id')}"
                )
                return None
        role_reasoning = result.get("role_reasoning", "")
        if any(
            p.lower() in role_reasoning.lower() for p in FORBIDDEN_IN_ROLE_REASONING
        ):
            logger.warning(
                f"role_reasoning contaminated with profile for offer {offer.get('id')} — retrying with stricter instruction"
            )
            retry_prompt = (
                prompt
                + "\n\nIMPORTANTE: role_reasoning NO debe mencionar al candidato ni su perfil. Describe solo el puesto."
            )
            try:
                retry = ollama_call(
                    model=model,
                    prompt=retry_prompt,
                    expect_json=True,
                    think=True,
                )
                if isinstance(retry, dict) and all(f in retry for f in required_fields):
                    retry_reasoning = retry.get("role_reasoning", "")
                    if not any(
                        p.lower() in retry_reasoning.lower()
                        for p in FORBIDDEN_IN_ROLE_REASONING
                    ):
                        result = retry
                        logger.info(f"Retry succeeded for offer {offer.get('id')}")
            except Exception:
                logger.warning(f"Retry also failed for offer {offer.get('id')}")
        role_reasoning = result.get("role_reasoning", "")
        if any(
            p.lower() in role_reasoning.lower() for p in FORBIDDEN_IN_ROLE_REASONING
        ):
            logger.warning(
                f"Fallback: storing contaminated result for offer {offer.get('id')} without role_reasoning"
            )
            result["role_reasoning"] = ""
            result["_contaminated"] = True
        raw_gaps = result.get("gap_types", [])
        if not isinstance(raw_gaps, list):
            logger.warning(
                f"gap_types is not a list: {type(raw_gaps).__name__} = {raw_gaps!r}"
            )
            raw_gaps = []
        # Ensure all elements are strings (gemma4 may return dicts)
        clean_gaps = [str(g) if not isinstance(g, str) else g for g in raw_gaps]
        result["gap_type"] = resolve_gap_type(clean_gaps)
        result["relevance_flag"] = GAP_TO_FLAG.get(result["gap_type"], "stretch")
        return result
    except Exception as e:
        logger.error(f"Error calling gemma4 for offer {offer.get('id')}: {e}")
        return None


def _run_logic(limit: int | None) -> None:
    """Core logic for classifying offers."""
    logger.info(
        "Starting role classifier (limit=%s)", limit if limit is not None else "all"
    )
    perfil_path = Path(__file__).resolve().parent.parent.parent / "PERFIL.md"
    if not perfil_path.exists():
        logger.error("PERFIL.md not found. Cannot continue.")
        return
    perfil_content = perfil_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_columns_exist(conn)
        catalog = get_role_catalog(conn)
        cursor = conn.cursor()
        query = """
            SELECT id, source_id, title, description_clean, description_raw, skills_required
            FROM offers
            WHERE relevance_flag IS NULL
        """
        params = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (limit,)
        cursor.execute(query, params)
        offers = cursor.fetchall()
        if not offers:
            logger.info("No unclassified offers found")
            return
        logger.info(f"Found {len(offers)} unclassified offers to process")
        classified_count = 0
        new_roles_added: list[str] = []
        relevance_distribution: dict[str, int] = {}
        for i, offer in enumerate(offers, 1):
            offer_dict = dict(offer)
            logger.info(
                f"Processing offer {i}/{len(offers)}: {offer_dict.get('title', 'N/A')[:50]}"
            )
            result = classify_offer(offer_dict, catalog, perfil_content)
            if result is None:
                logger.warning(f"Failed to classify offer {offer_dict['id']}")
                continue
            role_normalized = result["role_normalized"]
            relevance_flag = result["relevance_flag"]
            is_new_role = role_normalized not in catalog
            result["is_new_role"] = is_new_role
            if is_new_role:
                logger.info(f"Adding new role to catalog: {role_normalized}")
                catalog.append(role_normalized)
                new_roles_added.append(role_normalized)
                update_role_catalog(conn, catalog)
            cursor.execute(
                """UPDATE offers SET
                    role_normalized = ?, relevance_flag = ?,
                    gap_type = ?, role_reasoning = ?,
                    classification_reasoning = ?,
                    is_new_role = ?,
                    updated_at = datetime('now')
                   WHERE id = ?""",
                (
                    result["role_normalized"],
                    result["relevance_flag"],
                    result.get("gap_type", ""),
                    result.get("role_reasoning", ""),
                    result.get("reasoning", ""),
                    int(is_new_role),
                    offer_dict["id"],
                ),
            )
            classified_count += 1
            relevance_distribution[relevance_flag] = (
                relevance_distribution.get(relevance_flag, 0) + 1
            )
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(offers)} offers processed")
        conn.commit()
        logger.info(
            f"Classification complete: {classified_count} classified, {len(new_roles_added)} new roles, distribution: {relevance_distribution}"
        )
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        conn.close()


def run_classifier(limit: int = 0) -> int:
    """Función exportable para el orquestador. Devuelve número de ofertas clasificadas."""
    import os
    import sqlite3
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    db_path = PROJECT_ROOT / os.getenv("DB_PATH", "data/jobs.db")
    conn = sqlite3.connect(db_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM offers WHERE relevance_flag IS NULL"
    ).fetchone()[0]
    conn.close()
    if count == 0:
        return 0
    _run_logic(limit if limit > 0 else None)
    return count


def main() -> None:
    """Main function to classify unclassified offers."""
    parser = argparse.ArgumentParser(
        description="Classify unclassified job offers using gemma4."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max offers to process per run (default: all pending)",
    )
    args = parser.parse_args()
    _run_logic(args.limit)


if __name__ == "__main__":
    main()
