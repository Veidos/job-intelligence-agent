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
        from src.utils.candidate_profile import CandidateProfile

        candidate_skills_map = CandidateProfile.from_perfil(sample_perfil_text).skills_map
        mock_response = CASSETTES["evaluate_technical_core"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer, candidate_skills_map)

        assert len(result["skills_present"]) == 3
        assert result["skills_present"][0]["name"] == "Python"
        assert result["skills_present"][0]["present"] is True
        assert "reasoning" in result

    def test_technical_senior_mismatch(self, sample_offer_senior, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_technical
        from src.utils.candidate_profile import CandidateProfile

        candidate_skills_map = CandidateProfile.from_perfil(sample_perfil_text).skills_map
        mock_response = CASSETTES["evaluate_technical_senior"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer_senior, candidate_skills_map)

        assert len(result["skills_present"]) == 5
        assert result["skills_present"][1]["name"] == "PyTorch"
        assert result["skills_present"][1]["present"] is False

    def test_technical_junior_no_exp_required(
        self, sample_offer_no_exp, sample_perfil_text
    ):
        from src.pipeline.evaluate import evaluate_technical
        from src.utils.candidate_profile import CandidateProfile

        candidate_skills_map = CandidateProfile.from_perfil(sample_perfil_text).skills_map
        mock_response = CASSETTES["evaluate_technical_junior"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer_no_exp, candidate_skills_map)

        assert len(result["skills_present"]) == 2
        assert result["skills_present"][0]["present"] is True
        assert result["skills_present"][1]["present"] is True

    def test_technical_devuelve_dict_no_string(self, sample_offer, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_technical
        from src.utils.candidate_profile import CandidateProfile

        candidate_skills_map = CandidateProfile.from_perfil(sample_perfil_text).skills_map
        mock_response = CASSETTES["evaluate_technical_core"]

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_technical(sample_offer, candidate_skills_map)

        assert isinstance(result, dict)
        assert not isinstance(result, str)


class TestEvaluateHR:
    """Tests para evaluate_hr() con cassettes."""

    def test_hr_core(self, sample_offer, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_hr

        mock_response = CASSETTES["evaluate_hr_core"]
        skill_detail = {"core": [], "secondary": []}

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_hr(
                sample_offer,
                sample_perfil_text,
                skill_detail,
                M_core=0.8,
                M_sec=0.5,
                F_exp=0.6,
                employment_gap=3.7,
                gap_severity="medium",
            )

        assert result["context_fit"] == 0.6
        assert result["apply_signal"] == "maybe"
        assert result["verdict"] is not None

    def test_hr_senior_rejected(self, sample_offer_senior, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_hr

        mock_response = CASSETTES["evaluate_hr_senior"]
        skill_detail = {"core": [], "secondary": []}

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_hr(
                sample_offer_senior,
                sample_perfil_text,
                skill_detail,
                M_core=0.2,
                M_sec=0.1,
                F_exp=0.1,
                employment_gap=3.7,
                gap_severity="medium",
            )

        assert result["apply_signal"] == "no"
        assert result["environment_compatibility"] == "baja"

    def test_hr_temporal_yes(self, sample_offer_temporal, sample_perfil_text):
        from src.pipeline.evaluate import evaluate_hr

        mock_response = CASSETTES["evaluate_hr_temporal"]
        skill_detail = {"core": [], "secondary": []}

        with patch("src.pipeline.evaluate.ollama_call") as mock:
            mock.return_value = mock_response
            result = evaluate_hr(
                sample_offer_temporal,
                sample_perfil_text,
                skill_detail,
                M_core=0.6,
                M_sec=0.4,
                F_exp=0.8,
                employment_gap=3.7,
                gap_severity="medium",
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
                relevance_flag, experience_min
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1,
            ),
        )
        test_db.execute(
            "INSERT INTO cv_versions (version, is_active) VALUES ('test-v1', 1)"
        )

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
                    stats = run_evaluate(limit=1)

        assert stats["evaluated"] == 1
        assert stats["errors"] == 0
        assert len(stats["scores"]) == 1

        row = test_db.execute(
            "SELECT e.match_score, e.recommendation FROM offer_evaluations e "
            "JOIN offers o ON o.id = e.offer_id WHERE o.source_id = ?",
            ("RUN-EVAL-001",),
        ).fetchone()
        assert row is not None
        assert row[0] > 0

    def test_run_evaluate_calcula_score_correcto(
        self, test_db, test_conn, sample_offer, sample_perfil_text
    ):
        from src.pipeline.evaluate import run_evaluate

        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag, experience_min
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                1,
            ),
        )

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
                    stats = run_evaluate(limit=1)

        score = stats["scores"][0]
        assert 0 < score <= 1.0
