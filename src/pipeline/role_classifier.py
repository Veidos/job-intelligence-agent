"""Role classifier for job offers.

Classifies offers into roles from a catalog and assigns relevance flags.
Uses gemma4 for classification.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import argparse
from pathlib import Path
from typing import Any

from src.utils.ollama_client import ollama_call

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


def classify_offer(
    offer: dict[str, Any],
    catalog: list[str],
    perfil_content: str,
) -> dict[str, Any] | None:
    """Classify an offer using gemma4."""
    title = offer.get("title", "")
    description = offer.get("description_clean") or offer.get("description_raw") or ""
    if description:
        description = description[:2000]

    prompt = f"""Eres un clasificador de ofertas de empleo. 
Dado este catálogo de roles: {catalog}
Y este perfil de candidato: {perfil_content}

Analiza esta oferta:
Título: {title}
Descripción: {description}

Decide:
1. ¿A qué role del catálogo corresponde realmente esta oferta
   basándote en los REQUISITOS, no en el título?
2. Si no encaja en ninguno, propón un nombre nuevo en snake_case.
3. ¿Qué relevance_flag tiene para este candidato?
   core: requisitos coinciden >70% con el perfil
   adjacent: coinciden 40-70%
   stretch: coinciden 20-40%
   temporal: trabajo puente viable

Responde SOLO JSON:
{{
  "role_normalized": "nombre_del_catalogo_o_nuevo",
  "relevance_flag": "core|adjacent|stretch|temporal",
  "is_new_role": true|false,
  "reasoning": "string breve"
}}"""
    try:
        result = ollama_call(
            model="gemma4:e4b",
            prompt=prompt,
            expect_json=True,
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
            "relevance_flag",
            "is_new_role",
            "reasoning",
        ]
        for field in required_fields:
            if field not in result:
                logger.warning(
                    f"Missing field {field} in response for offer {offer.get('id')}"
                )
                return None
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
            SELECT id, source_id, title, description_clean, description_raw
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
            is_new_role = result["is_new_role"]
            if is_new_role and role_normalized not in catalog:
                logger.info(f"Adding new role to catalog: {role_normalized}")
                catalog.append(role_normalized)
                new_roles_added.append(role_normalized)
                update_role_catalog(conn, catalog)
            cursor.execute(
                "UPDATE offers SET role_normalized = ?, relevance_flag = ?, updated_at = datetime('now') WHERE id = ?",
                (role_normalized, relevance_flag, offer_dict["id"]),
            )
            classified_count += 1
            relevance_distribution[relevance_flag] = (
                relevance_distribution.get(relevance_flag, 0) + 1
            )
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(offers)} offers processed")
            time.sleep(0.5)
        conn.commit()
        logger.info(
            f"Classification complete: {classified_count} classified, {len(new_roles_added)} new roles, distribution: {relevance_distribution}"
        )
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise
    finally:
        conn.close()


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
