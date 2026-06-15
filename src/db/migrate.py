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

SCHEMA_DEFINITIONS = {
    "companies": [
        ("infojobs_company_id", "TEXT"),
        ("name", "TEXT NOT NULL"),
        ("sector", "TEXT"),
        ("size_range", "TEXT"),
        ("rating_overall", "REAL"),
        ("rating_worklife", "REAL"),
        ("rating_culture", "REAL"),
        ("rating_growth", "REAL"),
        ("reviews_count", "INTEGER DEFAULT 0"),
        ("reviews_sample", "TEXT"),
        ("avg_inscriptions", "INTEGER"),
        ("offers_published_30d", "INTEGER"),
        ("response_rate_signal", "TEXT DEFAULT 'desconocida'"),
        ("llm_description", "TEXT"),
        ("green_flags", "TEXT"),
        ("red_flags", "TEXT"),
        ("llm_confidence", "TEXT"),
        ("enriched_by_llm_at", "DATETIME"),
        ("llm_model", "TEXT"),
        ("first_seen_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("last_updated_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
    ],
    "cv_versions": [
        ("version", "TEXT NOT NULL"),
        ("filename", "TEXT"),
        ("uploaded_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("content_parsed", "TEXT"),
        ("is_active", "INTEGER NOT NULL DEFAULT 1"),
    ],
    "apify_raw_responses": [
        ("run_id", "TEXT NOT NULL"),
        ("item_index", "INTEGER NOT NULL"),
        ("source_id", "TEXT"),
        ("fetched_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("payload", "TEXT NOT NULL"),
        ("processed", "INTEGER NOT NULL DEFAULT 0"),
        ("error", "TEXT"),
    ],
    "offers": [
        ("source_id", "TEXT NOT NULL UNIQUE"),
        ("source", "TEXT NOT NULL DEFAULT 'infojobs'"),
        ("url", "TEXT"),
        ("title", "TEXT NOT NULL"),
        ("company_id", "INTEGER REFERENCES companies(id)"),
        ("company_name", "TEXT"),
        ("employer_id", "TEXT"),
        ("province", "TEXT"),
        ("city", "TEXT"),
        ("salary_min", "REAL"),
        ("salary_max", "REAL"),
        ("salary_period", "TEXT"),
        ("contract_type", "TEXT"),
        ("work_mode", "TEXT"),
        ("experience_min", "INTEGER"),
        ("experience_max", "INTEGER"),
        ("education_level", "TEXT"),
        ("skills_required", "TEXT"),
        ("description_raw", "TEXT"),
        ("description_clean", "TEXT"),
        ("applications_count", "INTEGER DEFAULT 0"),
        ("views_count", "INTEGER DEFAULT 0"),
        ("published_at", "DATETIME"),
        ("expires_at", "DATETIME"),
        ("fetched_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("is_active", "INTEGER NOT NULL DEFAULT 1"),
        ("is_evaluated", "INTEGER NOT NULL DEFAULT 0"),
        ("search_layer", "INTEGER"),
        ("role_level", "INTEGER"),
        ("relevance_flag", "TEXT"),
        ("role_normalized", "TEXT"),
        ("classification_reasoning", "TEXT"),
        ("gap_type", "TEXT"),
        ("role_reasoning", "TEXT"),
        ("is_new_role", "INTEGER DEFAULT 0"),
        ("raw_data", "TEXT"),
        ("enriched_at", "TEXT"),
        ("role_level_label", "TEXT"),
    ],
    "offer_evaluations": [
        ("offer_id", "INTEGER NOT NULL REFERENCES offers(id)"),
        ("cv_version_id", "INTEGER REFERENCES cv_versions(id)"),
        ("evaluated_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("skills_hard_match", "INTEGER"),
        ("experience_match", "INTEGER"),
        ("location_match", "INTEGER"),
        ("market_competitiveness", "INTEGER"),
        ("scoring_detail", "TEXT"),
        ("match_score", "INTEGER"),
        ("recommendation", "TEXT"),
        ("environment_compatibility", "TEXT"),
        ("hr_concerns", "TEXT"),
        ("strengths", "TEXT"),
        ("red_flags", "TEXT"),
        ("gemma_verdict", "TEXT"),
        ("interview_prep", "TEXT"),
        ("apply_recommendation", "TEXT"),
        ("descarte_tipo", "TEXT DEFAULT 'ninguno'"),
        ("descarte_razon", "TEXT"),
        ("relevance_validation", "TEXT"),
        ("relevance_corrected", "TEXT"),
        ("relevance_reasoning", "TEXT"),
        ("apply_block", "TEXT"),
        ("apply_block_reason", "TEXT"),
        ("llm_apply_signal", "TEXT"),
        ("model_technical", "TEXT DEFAULT 'gemma4:e4b'"),
        ("model_hr", "TEXT DEFAULT 'gemma4:e4b'"),
        ("processing_ms", "INTEGER"),
        ("sent_via_telegram", "INTEGER DEFAULT 0"),
        ("sent_at", "DATETIME"),
        ("daily_position", "INTEGER"),
    ],
    "user_feedback": [
        ("offer_id", "INTEGER REFERENCES offers(id)"),
        ("feedback_type", "TEXT NOT NULL"),
        ("raw_text", "TEXT NOT NULL"),
        ("processed", "INTEGER DEFAULT 0"),
    ],
    "user_psychology": [
        ("raw_feedback", "TEXT"),
        ("summary", "TEXT"),
        ("key_insights", "TEXT"),
        ("version", "INTEGER DEFAULT 1"),
    ],
    "search_config": [
        ("generated_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("cv_version_id", "INTEGER REFERENCES cv_versions(id)"),
        ("geo_hierarchy", "TEXT"),
        ("role_hierarchy", "TEXT"),
        ("active_geo_level", "INTEGER"),
        ("active_role_level", "INTEGER"),
        ("last_full_fetch", "DATETIME"),
        ("last_updated", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("role_catalog", "TEXT"),
    ],
    "applications": [
        ("offer_id", "INTEGER NOT NULL REFERENCES offers(id)"),
        ("applied_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("status", "TEXT NOT NULL DEFAULT 'applied'"),
        ("notes", "TEXT"),
        ("contact_name", "TEXT"),
        ("next_action_date", "TEXT"),
        ("created_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
        ("updated_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
    ],
    "user_settings": [
        ("key", "TEXT NOT NULL UNIQUE"),
        ("value", "TEXT"),
        ("updated_at", "DATETIME NOT NULL DEFAULT (datetime('now'))"),
    ],
}


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


def run_migration() -> dict:
    """Ejecuta la migración del schema."""
    log.info("Iniciando migración de schema...")

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

    for table_name, columns in SCHEMA_DEFINITIONS.items():
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

    return {"added": total_added, "tables": len(SCHEMA_DEFINITIONS)}


if __name__ == "__main__":
    run_migration()
