"""Integration tests para evaluate.py usando Ollama cassettes (mocked).

Los cassettes son respuestas JSON pre-grabadas de gemma4:e4b.
Se usan patches en mock_ollama_call para simular respuestas del modelo.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.ollama import CASSETTES  # noqa: E402


class TestEvaluateTechnical:
    """Tests para evaluate_technical() con cassettes."""

    def test_technical_core_match(
        self, test_db, test_conn, sample_offer, sample_perfil_text
    ):
        from src.pipeline.evaluate import evaluate_technical

        mock_response = CASSETTES["evaluate_technical_core"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer, sample_perfil_text)

        assert result["skills_hard_match"] == 22
        assert result["experience_match"] == 15
        assert result["education_match"] == 7
        assert result["location_match"] == 5
        assert "nivel_match_reasoning" in result
        assert "reasoning" in result

    def test_technical_senior_mismatch(self, sample_offer_senior, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_technical

        mock_response = CASSETTES["evaluate_technical_senior"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer_senior, sample_perfil_text)

        assert result["skills_hard_match"] == 8
        assert result["experience_match"] == 5

    def test_technical_junior_no_exp_required(
        self, sample_offer_no_exp, sample_perfil_text
    ):
        from src.pipeline.evaluate import evaluate_technical

        mock_response = CASSETTES["evaluate_technical_junior"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer_no_exp, sample_perfil_text)

        assert result["experience_match"] == 18
        assert result["location_match"] == 5

    def test_technical_devuelve_dict_no_string(self, sample_offer, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_technical

        mock_response = CASSETTES["evaluate_technical_core"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer, sample_perfil_text)

        assert isinstance(result, dict)
        assert not isinstance(result, str)

    def test_technical_usa_perfil_completo(self, sample_offer):
        from src.pipeline.evaluate import evaluate_technical

        mock_response = CASSETTES["evaluate_technical_core"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer, "")

        assert isinstance(result, dict)


class TestEvaluateHR:
    """Tests para evaluate_hr() con cassettes."""

    def test_hr_core(self, sample_offer, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_hr

        mock_response = CASSETTES["evaluate_hr_core"]
        technical = {
            "skills_hard_match": 22,
            "experience_match": 15,
            "education_match": 7,
            "location_match": 5,
        }

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_hr(
                sample_offer, sample_perfil_text, technical, employment_gap=3.7
            )

        assert result["trajectory_coherence"] == 9
        assert result["recency_relevance"] == 4
        assert result["market_competitiveness"] == 3
        assert result["penalty"] == 12
        assert result["apply_signal"] == "maybe"
        assert result["verdict"] is not None
        assert "gap_laboral_3_7_anios" in result["penalty_breakdown"]

    def test_hr_senior_rejected(self, sample_offer_senior, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_hr

        mock_response = CASSETTES["evaluate_hr_senior"]
        technical = {
            "skills_hard_match": 8,
            "experience_match": 5,
            "education_match": 4,
            "location_match": 2,
        }

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_hr(
                sample_offer_senior, sample_perfil_text, technical, employment_gap=3.7
            )

        assert result["apply_signal"] == "no"
        assert result["penalty"] == 20
        assert result["environment_compatibility"] == "baja"

    def test_hr_temporal_yes(self, sample_offer_temporal, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_hr

        mock_response = CASSETTES["evaluate_hr_temporal"]
        technical = {
            "skills_hard_match": 15,
            "experience_match": 18,
            "education_match": 8,
            "location_match": 5,
        }

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_hr(
                sample_offer_temporal, sample_perfil_text, technical, employment_gap=3.7
            )

        assert result["apply_signal"] == "yes"
        assert result["environment_compatibility"] == "alta"


class TestRunEvaluateWithCassettes:
    """Tests de integración de run_evaluate() completo con cassettes."""

    def test_run_evaluate_procesa_oferta_y_guarda_en_db(
        self, test_db, test_conn, sample_offer, sample_perfil_text
    ):
        from src.pipeline.evaluate import run_evaluate

        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RUN-EVAL-001",
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
            "INSERT INTO cv_versions (version, is_active) VALUES ('test-v1', 1)"
        )

        tech_response = CASSETTES["evaluate_technical_core"]
        hr_response = CASSETTES["evaluate_hr_core"]

        call_count = 0

        def mock_ollama_call(model, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tech_response
            elif call_count == 2:
                return hr_response
            return {}

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            with patch(
                "src.pipeline.evaluate.load_perfil", return_value=sample_perfil_text
            ):
                with patch(
                    "src.pipeline.evaluate.ollama_call", side_effect=mock_ollama_call
                ):
                    stats = run_evaluate(limit=1)

        assert stats["evaluated"] == 1
        assert stats["errors"] == 0
        assert stats["descarte"] == 0
        assert len(stats["scores"]) == 1

        row = test_db.execute(
            "SELECT match_score, recommendation FROM offer_evaluations WHERE offer_id = 1"
        ).fetchone()
        assert row is not None
        assert row[0] > 0

    def test_run_evaluate_descarta_requisito_imposible(
        self, test_db, test_conn, sample_offer_with_impossible_requirements
    ):
        from src.pipeline.evaluate import run_evaluate

        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RUN-DESC-001",
                sample_offer_with_impossible_requirements["title"],
                sample_offer_with_impossible_requirements["company_name"],
                sample_offer_with_impossible_requirements["city"],
                sample_offer_with_impossible_requirements["work_mode"],
                sample_offer_with_impossible_requirements["description_clean"],
                sample_offer_with_impossible_requirements["skills_required"],
                0,
                1,
                "stretch",
            ),
        )

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            with patch("src.pipeline.evaluate.load_perfil", return_value=""):
                with patch("src.pipeline.evaluate.ollama_call"):
                    stats = run_evaluate(limit=1)

        assert stats["evaluated"] == 1
        assert stats["descarte"] == 1
        assert stats["scores"] == []

        row = test_db.execute(
            "SELECT match_score, recommendation, descarte_tipo FROM offer_evaluations WHERE offer_id = 1"
        ).fetchone()
        assert row[0] == 0
        assert row[1] == "Descartado"
        assert row[2] == "requisito_imposible"

    def test_run_evaluate_calcula_score_correcto(
        self, test_db, test_conn, sample_offer, sample_perfil_text
    ):
        from src.pipeline.evaluate import run_evaluate

        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RUN-SCORE-001",
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

        tech_response = CASSETTES["evaluate_technical_core"]
        hr_response = CASSETTES["evaluate_hr_core"]

        call_count = 0

        def mock_ollama_call(model, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return tech_response
            elif call_count == 2:
                return hr_response
            return {}

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            with patch(
                "src.pipeline.evaluate.load_perfil", return_value=sample_perfil_text
            ):
                with patch(
                    "src.pipeline.evaluate.ollama_call", side_effect=mock_ollama_call
                ):
                    stats = run_evaluate(limit=1)

        score = stats["scores"][0]
        expected = (22 + 15 + 7 + 5) + (9 + 4 + 3) - 12
        assert score == expected
        assert 35 <= score <= 100
