"""Script de migración de schema.

Añade columnas que faltan a las tablas existentes en jobs.db.
Ejecutable standalone: python -m src.db.migrate
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

def get_existing_columns(conn, table_name: str) -> set[str]:
    """Obtiene las columnas existentes de una tabla."""
    cur = conn.cursor()
    rows = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def migrate_table(conn, table_name: str, columns: list[tuple]) -> list[str]:
    """Migra una tabla añadiendo las columnas que faltan."""
    existing = get_existing_columns(conn, table_name)
    added = []

    for col_name, col_def in columns:
        if col_name.lower() not in {c.lower() for c in existing}:
            try:
                conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")
                added.append(col_name)
                log.info("  Añadida columna %s.%s", table_name, col_name)
            except Exception as e:
                log.warning(
                    "  Error añadiendo %s.%s: %s",
                    table_name,
                    col_name,
                    e,
                )

    return added


ZOMBIE_COLUMNS = [
    "education_match",
    "trajectory_coherence",
    "recency_relevance",
    "penalty",
    "company_fit_score",
    "company_green_flags",
    "company_red_flags",
]


def drop_zombie_columns(conn) -> list[str]:
    """Elimina columnas zombies de offer_evaluations y renombra penalty_breakdown."""
    existing = get_existing_columns(conn, "offer_evaluations")
    dropped = []

    for col in ZOMBIE_COLUMNS:
        if col.lower() in {c.lower() for c in existing}:
            try:
                conn.execute(f"ALTER TABLE offer_evaluations DROP COLUMN {col}")
                dropped.append(col)
                log.info("  Eliminada columna offer_evaluations.%s", col)
            except Exception as e:
                log.warning("  Error eliminando %s: %s", col, e)

    # Renombrar penalty_breakdown → scoring_detail
    if "penalty_breakdown" in existing and "scoring_detail" not in existing:
        try:
            conn.execute(
                "ALTER TABLE offer_evaluations RENAME COLUMN penalty_breakdown TO scoring_detail"
            )
            dropped.append("penalty_breakdown → scoring_detail")
            log.info("  Renombrada penalty_breakdown → scoring_detail")
        except Exception as e:
            log.warning("  Error renombrando penalty_breakdown: %s", e)

    return dropped


OFFERS_ZOMBIE_COLUMNS = [
    "role_level",
    "role_level_label",
]


def drop_offers_zombie_columns(conn) -> list[str]:
    """Elimina columnas zombies de offers (legacy del scoring con role_level_label)."""
    existing = get_existing_columns(conn, "offers")
    dropped = []

    for col in OFFERS_ZOMBIE_COLUMNS:
        if col.lower() in {c.lower() for c in existing}:
            try:
                conn.execute(f"ALTER TABLE offers DROP COLUMN {col}")
                dropped.append(col)
                log.info("  Eliminada columna offers.%s", col)
            except Exception as e:
                log.warning("  Error eliminando offers.%s: %s", col, e)

    return dropped


def _parse_schema_columns(schema_sql: str) -> dict[str, list[tuple[str, str]]]:
    """Extrae columnas por tabla desde los CREATE TABLE de schema.sql.

    Devuelve: {"tabla": [("col_name", "col_def"), ...]}
    Solo extrae columnas simples (no PRIMARY KEY, FOREIGN KEY, etc.).
    """
    import re

    result: dict[str, list[tuple[str, str]]] = {}

    for table_match in re.finditer(
        r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?(\w+)\s*\((.*?)\);",
        schema_sql,
        re.DOTALL | re.IGNORECASE,
    ):
        table_name = table_match.group(1)
        body = table_match.group(2)
        cols = []
        for raw_line in body.split("\n"):
            line = raw_line.split("--")[0].strip().rstrip(",").strip()
            if not line:
                continue
            upper = line.upper()
            if any(
                upper.startswith(kw)
                for kw in (
                    "PRIMARY KEY",
                    "FOREIGN KEY",
                    "UNIQUE",
                    "CHECK",
                    "CONSTRAINT",
                    "CREATE",
                    "PRAGMA",
                )
            ):
                continue
            parts = line.split(None, 1)
            if len(parts) >= 2:
                col_name = parts[0]
                col_def = parts[1].rstrip(",").strip()
                if col_name.lower() == "id":
                    continue
                cols.append((col_name, col_def))
        if cols:
            result[table_name] = cols
    return result


def run_migration() -> dict:
    """Ejecuta la migración del schema."""
    log.info("Iniciando migración de schema...")

    schema_path = Path(__file__).resolve().parents[2] / "src" / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    schema_definitions = _parse_schema_columns(schema_sql)

    conn = get_connection()
    total_added = 0

    # Crear tablas nuevas que no existían en versiones anteriores de la DB
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apify_raw_responses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id       TEXT NOT NULL,
            item_index   INTEGER NOT NULL,
            source_id    TEXT,
            fetched_at   DATETIME NOT NULL DEFAULT (datetime('now')),
            payload      TEXT NOT NULL,
            processed    INTEGER NOT NULL DEFAULT 0,
            error        TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apify_raw_run_id    ON apify_raw_responses(run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apify_raw_source_id ON apify_raw_responses(source_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_apify_raw_processed ON apify_raw_responses(processed)"
    )
    conn.commit()
    log.info("Tabla apify_raw_responses verificada")

    # Crear tabla scraper_raw_responses si no existe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scraper_raw_responses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id     TEXT NOT NULL,
            offer_id   TEXT,
            payload    TEXT NOT NULL,
            processed  INTEGER NOT NULL DEFAULT 0,
            error      TEXT,
            created_at DATETIME NOT NULL DEFAULT (datetime('now')),
            UNIQUE(offer_id)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scraper_raw_run_id ON scraper_raw_responses(run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scraper_raw_offer_id ON scraper_raw_responses(offer_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scraper_raw_processed ON scraper_raw_responses(processed)"
    )
    conn.commit()
    log.info("Tabla scraper_raw_responses verificada")

    # Crear tabla applications si no existe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER NOT NULL REFERENCES offers(id),
            applied_at DATETIME NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'applied',
            notes TEXT,
            contact_name TEXT,
            next_action_date TEXT,
            created_at DATETIME NOT NULL DEFAULT (datetime('now')),
            updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_offer_id ON applications(offer_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_applications_applied_at ON applications(applied_at)"
    )
    conn.commit()
    log.info("Tabla applications verificada")

    # Fase 2: limpieza de columnas zombies (solo si existen)
    dropped_cols = drop_zombie_columns(conn)
    if dropped_cols:
        conn.commit()
        log.info("Limpieza completada: %d columnas procesadas", len(dropped_cols))

    offers_dropped = drop_offers_zombie_columns(conn)
    if offers_dropped:
        conn.commit()
        log.info(
            "Limpieza offers completada: %d columnas procesadas",
            len(offers_dropped),
        )

    for table_name, columns in schema_definitions.items():
        try:
            existing = get_existing_columns(conn, table_name)
            if not existing:
                log.warning("  Tabla %s no existe, saltando", table_name)
                continue

            added = migrate_table(conn, table_name, columns)
            if added:
                log.info("Tabla %s: %d columnas añadidas", table_name, len(added))
                total_added += len(added)
            else:
                log.debug("Tabla %s: ya actualizada", table_name)

        except Exception as e:
            log.error("Error migrando tabla %s: %s", table_name, e)

    conn.close()

    if total_added == 0:
        log.info("Schema ya actualizado")
    else:
        log.info("Migración completada: %d columnas añadidas", total_added)

    return {"added": total_added, "tables": len(schema_definitions)}


if __name__ == "__main__":
    run_migration()
