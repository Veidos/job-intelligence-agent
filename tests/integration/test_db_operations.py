"""Integration tests para DB — offers, evaluations, constraints, queries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestOffersTable:
    """Tests para la tabla offers."""

    def test_insert_and_retrieve(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INSERT-001",
                "Data Analyst Junior",
                "TechCorp",
                "Madrid",
                "Remoto",
                "Descripción de prueba",
                '["Python", "SQL"]',
                0,
                1,
                "core",
            ),
        )

        row = test_db.execute(
            "SELECT title, company_name, city FROM offers WHERE source_id = ?",
            ("INSERT-001",),
        ).fetchone()

        assert row is not None
        assert row[0] == "Data Analyst Junior"
        assert row[1] == "TechCorp"
        assert row[2] == "Madrid"

    def test_unique_source_id_constraint(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DUPE-001",
                "Original",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                0,
                1,
                "core",
            ),
        )

        with pytest.raises(Exception):
            test_db.execute(
                """
                INSERT INTO offers (
                    source_id, title, company_name, city, work_mode,
                    description_clean, skills_required, is_evaluated, is_active,
                    relevance_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "DUPE-001",
                    "Duplicado",
                    "Corp",
                    "Madrid",
                    "Remoto",
                    "Desc",
                    "[]",
                    0,
                    1,
                    "core",
                ),
            )

    def test_is_evaluated_flag(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVAL-FLAG",
                "Test",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )

        row = test_db.execute(
            "SELECT is_evaluated FROM offers WHERE source_id = ?", ("EVAL-FLAG",)
        ).fetchone()

        assert row[0] == 1

    def test_soft_delete_is_active_false(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "INACTIVE",
                "Old Offer",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                0,
                "core",
            ),
        )

        row = test_db.execute(
            "SELECT is_active FROM offers WHERE source_id = ?", ("INACTIVE",)
        ).fetchone()

        assert row[0] == 0


class TestOfferEvaluationsTable:
    """Tests para la tabla offer_evaluations."""

    def test_insert_evaluation(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVAL-INSERT",
                "Test",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        offer_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        test_db.execute(
            """
            INSERT INTO offer_evaluations (
                offer_id, skills_hard_match, experience_match, education_match,
                location_match, trajectory_coherence, recency_relevance,
                market_competitiveness, penalty, match_score, recommendation,
                model_technical, model_hr, sent_via_telegram
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer_id,
                20,
                12,
                8,
                5,
                10,
                8,
                3,
                5,
                58,
                "Aplicar",
                "gemma4:e4b",
                "gemma4:e4b",
                0,
            ),
        )

        row = test_db.execute(
            "SELECT match_score, recommendation FROM offer_evaluations WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()

        assert row is not None
        assert row[0] == 58
        assert row[1] == "Aplicar"

    def test_json_fields_serialization(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVAL-JSON",
                "Test",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        offer_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        test_db.execute(
            """
            INSERT INTO offer_evaluations (
                offer_id, skills_hard_match, experience_match, education_match,
                location_match, trajectory_coherence, recency_relevance,
                market_competitiveness, penalty, penalty_breakdown, match_score,
                recommendation, hr_concerns, strengths, red_flags,
                model_technical, model_hr, sent_via_telegram
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer_id,
                20,
                12,
                8,
                5,
                10,
                8,
                3,
                5,
                '{"gap_laboral": -5}',
                58,
                "Aplicar",
                '["Empresa grande"]',
                '["Skills técnicas"]',
                "[]",
                "gemma4:e4b",
                "gemma4:e4b",
                0,
            ),
        )

        row = test_db.execute(
            "SELECT penalty_breakdown, hr_concerns FROM offer_evaluations WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()

        breakdown = json.loads(row[0])
        concerns = json.loads(row[1])

        assert breakdown["gap_laboral"] == -5
        assert concerns[0] == "Empresa grande"

    def test_mark_sent_updates_telegram_fields(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVAL-SENT",
                "Test",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        offer_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        test_db.execute(
            """
            INSERT INTO offer_evaluations (
                offer_id, skills_hard_match, experience_match, education_match,
                location_match, trajectory_coherence, recency_relevance,
                market_competitiveness, penalty, match_score, recommendation,
                model_technical, model_hr, sent_via_telegram
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer_id,
                20,
                12,
                8,
                5,
                10,
                8,
                3,
                5,
                58,
                "Aplicar",
                "gemma4:e4b",
                "gemma4:e4b",
                0,
            ),
        )
        eval_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        test_db.execute(
            """
            UPDATE offer_evaluations
            SET sent_via_telegram = 1, sent_at = datetime('now'), daily_position = 1
            WHERE id = ?
            """,
            (eval_id,),
        )

        row = test_db.execute(
            "SELECT sent_via_telegram, daily_position FROM offer_evaluations WHERE id = ?",
            (eval_id,),
        ).fetchone()

        assert row[0] == 1
        assert row[1] == 1


class TestQueryPendingOffers:
    """Tests para queries de ofertas pendientes."""

    def test_get_pending_offers_query(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PEND-1",
                "Pendiente",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                0,
                1,
                "core",
                "2026-01-15",
            ),
        )
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PEND-2",
                "Evaluada",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
                "2026-01-14",
            ),
        )
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PEND-3",
                "Sin Flag",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                0,
                1,
                None,
                "2026-01-13",
            ),
        )

        rows = test_db.execute(
            """
            SELECT source_id, title FROM offers
            WHERE relevance_flag IS NOT NULL AND is_evaluated = 0
            ORDER BY published_at DESC LIMIT 10
            """
        ).fetchall()

        assert len(rows) == 1
        assert rows[0][0] == "PEND-1"
        assert rows[0][1] == "Pendiente"

    def test_get_top_offers_query(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TOP-A",
                "Oferta A",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        oid_a = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 0)",
            (oid_a, 45, "Con expectativas bajas"),
        )

        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TOP-B",
                "Oferta B",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        oid_b = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 0)",
            (oid_b, 72, "Prioritario"),
        )

        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TOP-C",
                "Oferta C",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        oid_c = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 0)",
            (oid_c, 58, "Aplicar"),
        )

        rows = test_db.execute(
            """
            SELECT o.title, e.match_score FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.sent_via_telegram = 0 AND e.match_score >= 35
            ORDER BY e.match_score DESC LIMIT 3
            """
        ).fetchall()

        assert len(rows) == 3
        assert rows[0][0] == "Oferta B"
        assert rows[0][1] == 72
        assert rows[1][0] == "Oferta C"
        assert rows[1][1] == 58
        assert rows[2][0] == "Oferta A"
        assert rows[2][1] == 45

    def test_exclude_sent_offers(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SENT-OFFER",
                "Ya Enviada",
                "Corp",
                "Madrid",
                "Remoto",
                "Desc",
                "[]",
                1,
                1,
                "core",
            ),
        )
        oid = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 1)",
            (oid, 80, "Prioritario"),
        )

        count = test_db.execute(
            "SELECT COUNT(*) FROM offer_evaluations WHERE sent_via_telegram = 0 AND match_score >= 35"
        ).fetchone()[0]

        assert count == 0


class TestSearchConfigRoleCatalog:
    """Tests para search_config y role_catalog."""

    def test_insert_and_retrieve_role_catalog(self, test_db):
        catalog = json.dumps(["data_analyst", "data_scientist", "ml_engineer"])
        test_db.execute(
            "INSERT INTO search_config (role_catalog, generated_at) VALUES (?, datetime('now'))",
            (catalog,),
        )

        row = test_db.execute(
            "SELECT role_catalog FROM search_config ORDER BY id DESC LIMIT 1"
        ).fetchone()
        loaded = json.loads(row[0])

        assert len(loaded) == 3
        assert "data_analyst" in loaded
        assert "ml_engineer" in loaded

    def test_update_role_catalog(self, test_db):
        initial_catalog = json.dumps(["data_analyst"])
        test_db.execute(
            "INSERT INTO search_config (role_catalog, generated_at) VALUES (?, datetime('now'))",
            (initial_catalog,),
        )
        config_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        new_catalog = json.dumps(["data_analyst", "data_engineer", "bi_analyst"])
        test_db.execute(
            "UPDATE search_config SET role_catalog = ?, last_updated = datetime('now') WHERE id = ?",
            (new_catalog, config_id),
        )

        row = test_db.execute(
            "SELECT role_catalog FROM search_config WHERE id = ?", (config_id,)
        ).fetchone()
        updated = json.loads(row[0])

        assert len(updated) == 3
        assert "bi_analyst" in updated
