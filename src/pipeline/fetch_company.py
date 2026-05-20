"""Enriquecimiento de datos de empresas.

Pobla la tabla companies con datos derivados de las ofertas existentes.
Usa employer_id (identificador único de InfoJobs) para deduplicar.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"


def get_employer_ids_from_offers(conn, limit: int = 50) -> list[dict]:
    """Obtiene employer_ids únicos de ofertas que no tienen company_id."""
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT DISTINCT employer_id, company_name
        FROM offers
        WHERE employer_id IS NOT NULL
          AND (company_id IS NULL OR company_id = 0)
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{"employer_id": r[0], "company_name": r[1]} for r in rows]


def company_exists(conn, employer_id: str) -> tuple[int | None, datetime | None]:
    """Check if company exists and when it was last updated."""
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, last_updated_at FROM companies WHERE infojobs_company_id = ?",
        (employer_id,),
    ).fetchone()
    if row:
        last_updated = datetime.fromisoformat(row[1].replace("Z", "+00:00"))
        return row[0], last_updated
    return None, None


def upsert_company(conn, employer_id: str, company_name: str) -> tuple[bool, bool]:
    """
    Inserta o actualiza una empresa.

    Returns:
        (is_new, is_updated) - tuple indicando si fue nueva y/o actualizada
    """
    cur = conn.cursor()

    company_id, last_updated = company_exists(conn, employer_id)
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)

    is_new = company_id is None
    is_updated = False

    if is_new:
        cur.execute(
            """
            INSERT INTO companies (
                infojobs_company_id, name, first_seen_at, last_updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (employer_id, company_name, now.isoformat(), now.isoformat()),
        )
        log.debug("Nueva empresa: %s (%s)", company_name, employer_id)
    elif last_updated and last_updated < seven_days_ago:
        cur.execute(
            """
            UPDATE companies SET name = ?, last_updated_at = ?
            WHERE id = ?
            """,
            (company_name, now.isoformat(), company_id),
        )
        is_updated = True
        log.debug("Empresa actualizada: %s (%s)", company_name, employer_id)
    else:
        log.debug(
            "Empresa actualizada recientemente: %s (%s)", company_name, employer_id
        )

    conn.commit()
    return is_new, is_updated


def get_unlinked_offers_count(conn) -> int:
    """Cuenta ofertas sin company_idlinked."""
    cur = conn.cursor()
    count = cur.execute(
        """
        SELECT COUNT(*) FROM offers
        WHERE employer_id IS NOT NULL AND (company_id IS NULL OR company_id = 0)
        """,
    ).fetchone()[0]
    return count


def link_offers_to_companies(conn) -> int:
    """Asocia ofertas con companies basándose en employer_id."""
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE OR IGNORE offers
        SET company_id = (
            SELECT c.id FROM companies c
            WHERE c.infojobs_company_id = offers.employer_id
        )
        WHERE employer_id IS NOT NULL AND company_id IS NULL
        """,
    )
    conn.commit()
    return cur.rowcount


def run(limit: int = 50) -> dict[str, Any]:
    """Función principal: pobla companies desde ofertas existentes."""
    conn = get_connection()

    pending = get_unlinked_offers_count(conn)
    log.info("[Enrich] Ofertas pendientes de enrichment: %d", pending)

    if pending == 0:
        log.info("[Enrich] No hay ofertas pendientes")
        conn.close()
        return {"new": 0, "updated": 0, "linked": 0, "pending": 0}

    employer_data = get_employer_ids_from_offers(conn, limit)

    if not employer_data:
        conn.close()
        return {"new": 0, "updated": 0, "linked": 0, "pending": pending}

    new_count = 0
    updated_count = 0

    for data in employer_data:
        try:
            is_new, is_updated = upsert_company(
                conn,
                data["employer_id"],
                data["company_name"] or "Empresa Desconocida",
            )
            if is_new:
                new_count += 1
            elif is_updated:
                updated_count += 1
        except Exception as e:
            log.warning(
                "[Enrich] Error procesando empresa %s: %s", data["employer_id"], e
            )
            continue

    linked_count = link_offers_to_companies(conn)

    remaining = get_unlinked_offers_count(conn)

    conn.close()

    log.info(
        "[Enrich] Completado: %d nuevas, %d actualizadas, %d enlazadas, %d pendientes",
        new_count,
        updated_count,
        linked_count,
        remaining,
    )

    return {
        "new": new_count,
        "updated": updated_count,
        "linked": linked_count,
        "pending": remaining,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enriquecer datos de empresas")
    parser.add_argument(
        "--limit", type=int, default=50, help="Límite de empresas a procesar"
    )
    args = parser.parse_args()

    result = run(args.limit)
    print(f"Resultado: {result}")
