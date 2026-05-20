"""Integration tests para save_evaluation y lógica de evaluación."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestSaveEvaluation:
    """Tests para save_evaluation()."""

    def test_guarda_evaluacion_completa(self, test_db, test_conn):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVAL-001",
                "Data Analyst",
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
        offer_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            from src.pipeline.evaluate import save_evaluation

            save_evaluation(
                offer_id=offer_id,
                technical={
                    "skills_hard_match": 20,
                    "experience_match": 12,
                    "education_match": 8,
                    "location_match": 5,
                },
                hr={
                    "trajectory_coherence": 10,
                    "recency_relevance": 8,
                    "market_competitiveness": 3,
                    "penalty": 5,
                    "penalty_breakdown": {"gap_laboral": -5},
                    "environment_compatibility": "alta",
                    "hr_concerns": ["Empresa grande"],
                    "strengths": ["Skills técnicas"],
                    "red_flags": [],
                    "verdict": "Buen match para aplicar",
                    "apply_recommendation": "Aplicar",
                },
                match_score=58,
                recommendation="Aplicar",
                processing_ms=1500,
            )

        row = test_db.execute(
            "SELECT match_score, recommendation FROM offer_evaluations WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == 58
        assert row[1] == "Aplicar"

        row = test_db.execute(
            "SELECT is_evaluated FROM offers WHERE id = ?", (offer_id,)
        ).fetchone()
        assert row[0] == 1

    def test_guarda_descarte_por_requisito_imposible(self, test_db, test_conn):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DESC-001",
                "Prácticas",
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
        offer_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            from src.pipeline.evaluate import save_evaluation

            save_evaluation(
                offer_id=offer_id,
                technical={},
                hr={},
                match_score=0,
                recommendation="Descartado",
                processing_ms=50,
                descarte_tipo="requisito_imposible",
                descarte_razon="No es estudiante de último año",
            )

        row = test_db.execute(
            "SELECT match_score, recommendation, descarte_tipo FROM offer_evaluations WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
        assert row[0] == 0
        assert row[1] == "Descartado"
        assert row[2] == "requisito_imposible"

    def test_serializa_json_penalty_breakdown(self, test_db, test_conn):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "PEN-001",
                "Senior DS",
                "MegaCorp",
                "Barcelona",
                "Remoto",
                "Desc",
                "[]",
                0,
                1,
                "core",
            ),
        )
        offer_id = test_db.execute("SELECT last_insert_rowid()").fetchone()[0]

        with patch("src.pipeline.evaluate.get_connection", return_value=test_conn):
            from src.pipeline.evaluate import save_evaluation

            save_evaluation(
                offer_id=offer_id,
                technical={
                    "skills_hard_match": 15,
                    "experience_match": 10,
                    "education_match": 8,
                    "location_match": 3,
                },
                hr={
                    "trajectory_coherence": 8,
                    "recency_relevance": 6,
                    "market_competitiveness": 2,
                    "penalty": 10,
                    "penalty_breakdown": {"gap_laboral": -10, "senior_requerido": -5},
                    "environment_compatibility": "baja",
                    "hr_concerns": ["Gap laboral >3 años"],
                    "strengths": [],
                    "red_flags": ["Requisitos muy avanzados"],
                    "verdict": "No encaja para este perfil",
                    "apply_recommendation": "No aplicar",
                },
                match_score=42,
                recommendation="Con expectativas bajas",
                processing_ms=2000,
            )

        row = test_db.execute(
            "SELECT penalty_breakdown FROM offer_evaluations WHERE offer_id = ?",
            (offer_id,),
        ).fetchone()
        breakdown = json.loads(row[0])
        assert breakdown["gap_laboral"] == -10


class TestGetTopOffers:
    """Tests para la query de selección de ofertas en send.py."""

    def test_selecciona_por_match_score_descendente(self, test_db):
        self._insert_offer_and_eval(test_db, "TOP-001", 45)
        self._insert_offer_and_eval(test_db, "TOP-002", 72)
        self._insert_offer_and_eval(test_db, "TOP-003", 58)

        rows = test_db.execute(
            """
            SELECT offer_id, match_score FROM offer_evaluations
            WHERE sent_via_telegram = 0 AND match_score >= 35
            ORDER BY match_score DESC LIMIT 3
            """
        ).fetchall()

        assert len(rows) == 3
        assert rows[0][1] == 72
        assert rows[1][1] == 58
        assert rows[2][1] == 45

    def test_excluye_ofertas_ya_enviadas(self, test_db):
        self._insert_offer_and_eval(test_db, "SENT-001", 60)
        self._insert_offer_and_eval(test_db, "SENT-002", 55)
        test_db.execute(
            "UPDATE offer_evaluations SET sent_via_telegram = 1 WHERE offer_id IN (1)"
        )

        count = test_db.execute(
            "SELECT COUNT(*) FROM offer_evaluations WHERE sent_via_telegram = 0 AND match_score >= 35"
        ).fetchone()[0]

        assert count == 1

    def test_filtra_score_menor_35(self, test_db):
        self._insert_offer_and_eval(test_db, "LOW-001", 20)
        self._insert_offer_and_eval(test_db, "LOW-002", 34)

        count = test_db.execute(
            "SELECT COUNT(*) FROM offer_evaluations WHERE sent_via_telegram = 0 AND match_score >= 35"
        ).fetchone()[0]

        assert count == 0

    def _insert_offer_and_eval(self, test_db, source_id, match_score):
        test_db.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode,
                description_clean, skills_required, is_evaluated, is_active,
                relevance_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                "Oferta",
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
            "INSERT INTO offer_evaluations (offer_id, match_score, recommendation, sent_via_telegram) VALUES (?, ?, ?, 0)",
            (offer_id, match_score, "Aplicar"),
        )
