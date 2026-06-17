"""Pipeline tests — flujo completo del orquestador con cassettes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.ollama import CASSETTES  # noqa: E402


class TestPipelineEndToEnd:
    """Tests del flujo completo fetch→classify→evaluate→send con cassettes."""

    def test_evaluate_flow_con_pipeline_real(
        self, test_db, test_conn, sample_offer, sample_perfil_text
    ):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PIPE-001",
                sample_offer["title"],
                sample_offer["company_name"],
                sample_offer["city"],
                sample_offer["work_mode"],
                sample_offer["description_clean"],
                sample_offer["skills_required"],
                0,
                1,
                "core",
            ),
        )
        test_db.execute("INSERT INTO cv_versions (version, is_active) VALUES ('v1', 1)")

        tech_response = CASSETTES["evaluate_technical_core"]
        hr_response = CASSETTES["evaluate_hr_core"]
        final_response = CASSETTES["evaluate_final_core"]

        call_count = 0

        def mock_ollama_call(model, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tech_response
            elif call_count == 2:
                return hr_response
            elif call_count == 3:
                return final_response
            return {}

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            with patch(
                "src.pipeline.evaluate.load_perfil", return_value=sample_perfil_text
            ):
                with patch(
                    "src.pipeline.evaluate.ollama_call", side_effect=mock_ollama_call
                ):
                    from src.pipeline.evaluate import run_evaluate

                    stats = run_evaluate(limit=1)

        assert stats["evaluated"] == 1
        assert stats["errors"] == 0
        assert stats["scores"][0] > 0

        row = test_db.execute(
            "SELECT is_evaluated FROM offers WHERE source_id = ?", ("PIPE-001",)
        ).fetchone()
        assert row[0] == 1

    def test_multiple_ofertas_procesadas_en_orden(
        self, test_db, test_conn, sample_offer, sample_offer_no_exp, sample_perfil_text
    ):
        test_db.execute(
            """
            INSERT INTO offers (source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active, relevance_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PIPE-MULTI-1",
                sample_offer["title"],
                sample_offer["company_name"],
                sample_offer["city"],
                sample_offer["work_mode"],
                sample_offer["description_clean"],
                sample_offer["skills_required"],
                0,
                1,
                "core",
            ),
        )
        test_db.execute(
            """
            INSERT INTO offers (source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active, relevance_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PIPE-MULTI-2",
                sample_offer_no_exp["title"],
                sample_offer_no_exp["company_name"],
                sample_offer_no_exp["city"],
                sample_offer_no_exp["work_mode"],
                sample_offer_no_exp["description_clean"],
                sample_offer_no_exp["skills_required"],
                0,
                1,
                "core",
            ),
        )
        test_db.execute("INSERT INTO cv_versions (version, is_active) VALUES ('v1', 1)")

        tech_core = CASSETTES["evaluate_technical_core"]
        hr_core = CASSETTES["evaluate_hr_core"]
        final_response = CASSETTES["evaluate_final_core"]
        tech_junior = CASSETTES["evaluate_technical_junior"]
        hr_temporal = CASSETTES["evaluate_hr_temporal"]

        call_count = 0

        def mock_ollama_call(model, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tech_core
            elif call_count == 2:
                return hr_core
            elif call_count == 3:
                return final_response
            elif call_count == 4:
                return tech_junior
            elif call_count == 5:
                return hr_temporal
            elif call_count == 6:
                return final_response
            return {}

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            with patch(
                "src.pipeline.evaluate.load_perfil", return_value=sample_perfil_text
            ):
                with patch(
                    "src.pipeline.evaluate.ollama_call", side_effect=mock_ollama_call
                ):
                    from src.pipeline.evaluate import run_evaluate

                    stats = run_evaluate(limit=5)

        assert stats["evaluated"] == 2
        assert len(stats["scores"]) == 2

        evals = test_db.execute(
            "SELECT COUNT(*) FROM offer_evaluations e "
            "JOIN offers o ON o.id = e.offer_id "
            "WHERE o.source_id IN ('PIPE-MULTI-1', 'PIPE-MULTI-2')"
        ).fetchone()[0]
        assert evals == 2

    def test_avg_score_calculado_correctamente(
        self, test_db, test_conn, sample_offer, sample_offer_no_exp, sample_perfil_text
    ):
        test_db.execute(
            """
            INSERT INTO offers (source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active, relevance_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PIPE-SCORE-1",
                sample_offer["title"],
                sample_offer["company_name"],
                sample_offer["city"],
                sample_offer["work_mode"],
                sample_offer["description_clean"],
                sample_offer["skills_required"],
                0,
                1,
                "core",
            ),
        )
        test_db.execute(
            """
            INSERT INTO offers (source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active, relevance_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PIPE-SCORE-2",
                sample_offer_no_exp["title"],
                sample_offer_no_exp["company_name"],
                sample_offer_no_exp["city"],
                sample_offer_no_exp["work_mode"],
                sample_offer_no_exp["description_clean"],
                sample_offer_no_exp["skills_required"],
                0,
                1,
                "core",
            ),
        )
        test_db.execute("INSERT INTO cv_versions (version, is_active) VALUES ('v1', 1)")

        tech_core = CASSETTES["evaluate_technical_core"]
        hr_core = CASSETTES["evaluate_hr_core"]
        final_response = CASSETTES["evaluate_final_core"]
        tech_junior = CASSETTES["evaluate_technical_junior"]
        hr_temporal = CASSETTES["evaluate_hr_temporal"]

        call_count = 0

        def mock_ollama_call(model, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tech_core
            elif call_count == 2:
                return hr_core
            elif call_count == 3:
                return final_response
            elif call_count == 4:
                return tech_junior
            elif call_count == 5:
                return hr_temporal
            elif call_count == 6:
                return final_response
            return {}

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            with patch(
                "src.pipeline.evaluate.load_perfil", return_value=sample_perfil_text
            ):
                with patch(
                    "src.pipeline.evaluate.ollama_call", side_effect=mock_ollama_call
                ):
                    from src.pipeline.evaluate import run_evaluate

                    stats = run_evaluate(limit=5)

        expected_avg = round((stats["scores"][0] + stats["scores"][1]) / 2, 4)
        assert stats["avg_score"] == expected_avg


class TestPipelineScoreCalculation:
    """Tests para cálculos de score en el pipeline."""

    def test_score_bloque_a_componentes(self):
        from src.pipeline.evaluate import _clamp

        technical = {
            "skills_hard_match": 22,
            "experience_match": 15,
            "education_match": 7,
            "location_match": 5,
        }
        bloque_a = (
            _clamp(technical["skills_hard_match"], 0, 30)
            + _clamp(technical["experience_match"], 0, 20)
            + _clamp(technical["education_match"], 0, 10)
            + _clamp(technical["location_match"], 0, 5)
        )
        assert bloque_a == 49

    def test_score_bloque_b_componentes(self):
        from src.pipeline.evaluate import _clamp

        hr = {
            "trajectory_coherence": 9,
            "recency_relevance": 4,
            "market_competitiveness": 3,
        }
        bloque_b = (
            _clamp(hr["trajectory_coherence"], 0, 15)
            + _clamp(hr["recency_relevance"], 0, 15)
            + _clamp(hr["market_competitiveness"], 0, 5)
        )
        assert bloque_b == 16

    def test_score_final_con_penalty(self):

        bloque_a = 49
        bloque_b = 16
        penalty = 12
        raw_score = bloque_a + bloque_b - penalty
        assert raw_score == 53

        capped = max(0, min(100, raw_score))
        assert 35 <= capped < 55

    def test_score_maximo_no_excede_100(self):

        bloque_a = 65
        bloque_b = 35
        penalty = 0
        score = max(0, min(100, bloque_a + bloque_b - penalty))
        assert score == 100

    def test_score_minimo_no_bajo_0(self):

        bloque_a = 10
        bloque_b = 5
        penalty = 50
        score = max(0, min(100, bloque_a + bloque_b - penalty))
        assert score == 0


class TestPipelineTelegramFormatting:
    """Tests de formato de salida para Telegram."""

    def test_top_offers_excluye_bajo_score(self, test_db):
        test_db.execute(
            """
            INSERT INTO offers (source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active, relevance_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TELE-001",
                "Oferta Alta",
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
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 0)",
            (oid, 75, "Prioritario"),
        )

        test_db.execute(
            """
            INSERT INTO offers (source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active, relevance_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "TELE-002",
                "Oferta Baja",
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
        oid2 = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 0)",
            (oid2, 20, "No aplicar"),
        )

        rows = test_db.execute(
            """
            SELECT o.title, e.match_score FROM offer_evaluations e
            JOIN offers o ON o.id = e.offer_id
            WHERE e.sent_via_telegram = 0 AND e.match_score >= 35
            ORDER BY e.match_score DESC LIMIT 3
            """
        ).fetchall()

        assert len(rows) == 1
        assert rows[0][0] == "Oferta Alta"
        assert rows[0][1] == 75

    def test_get_top_offers_date_scope_latest(self, test_db, test_conn):
        from src.telegram.send import get_top_offers

        now = "2026-06-16 12:00:00"
        yesterday = "2026-06-15 12:00:00"

        test_db.execute(
            "INSERT INTO offers (source_id, title, company_name, city, work_mode, "
            "description_clean, skills_required, is_evaluated, is_active, relevance_flag, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("D1-OF1", "Hoy Data Analyst", "Corp", "Madrid", "Remoto", "Desc", "[]", 1, 1, "core", now),
        )
        oid_today = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) "
            "VALUES (?, ?, ?, 0)",
            (oid_today, 55, "Con expectativas bajas"),
        )

        test_db.execute(
            "INSERT INTO offers (source_id, title, company_name, city, work_mode, "
            "description_clean, skills_required, is_evaluated, is_active, relevance_flag, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("D1-OF2", "Ayer Data Analyst", "Corp", "Madrid", "Remoto", "Desc", "[]", 1, 1, "core", yesterday),
        )
        oid_yesterday = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) "
            "VALUES (?, ?, ?, 0)",
            (oid_yesterday, 72, "Aplicar"),
        )

        with patch("src.telegram.send.get_connection", return_value=test_conn):
            result = get_top_offers(max_offers=5, date_scope='latest')

        assert len(result) == 1
        assert result[0]["title"] == "Hoy Data Analyst"
        assert result[0]["match_score"] == 55

    def test_get_top_offers_date_scope_all(self, test_db, test_conn):
        from src.telegram.send import get_top_offers

        now = "2026-06-16 12:00:00"
        yesterday = "2026-06-15 12:00:00"

        test_db.execute(
            "INSERT INTO offers (source_id, title, company_name, city, work_mode, "
            "description_clean, skills_required, is_evaluated, is_active, relevance_flag, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("D2-OF1", "Hoy Oferta", "Corp", "Madrid", "Remoto", "Desc", "[]", 1, 1, "core", now),
        )
        oid_today = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) "
            "VALUES (?, ?, ?, 0)",
            (oid_today, 60, "Aplicar"),
        )

        test_db.execute(
            "INSERT INTO offers (source_id, title, company_name, city, work_mode, "
            "description_clean, skills_required, is_evaluated, is_active, relevance_flag, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("D2-OF2", "Ayer Oferta", "Corp", "Madrid", "Remoto", "Desc", "[]", 1, 1, "core", yesterday),
        )
        oid_yesterday = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]
        test_db.execute(
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) "
            "VALUES (?, ?, ?, 0)",
            (oid_yesterday, 72, "Aplicar"),
        )

        with patch("src.telegram.send.get_connection", return_value=test_conn):
            result = get_top_offers(max_offers=5, date_scope='all')

        assert len(result) == 2
        assert result[0]["match_score"] == 72
        assert result[1]["match_score"] == 60
