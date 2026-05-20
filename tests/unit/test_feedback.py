"""Tests para el sistema de feedback."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


class TestGetLatestDailyOffers:
    """Tests para get_latest_daily_offers()."""

    def test_get_latest_daily_offers_empty(self):
        """DB vacía → lista vacía."""
        with patch("src.telegram.handlers.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.cursor.return_value = mock_cursor

            from src.telegram.handlers import get_latest_daily_offers

            result = get_latest_daily_offers()
            assert result == []

    def test_get_latest_daily_offers_filters_by_date(self):
        """Verifica que la query filtra correctamente por fecha."""
        import sqlite3
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=WAL")

            schema = Path("src/db/schema.sql").read_text()
            conn.executescript(schema)
            conn.commit()

            conn.execute(
                "INSERT INTO offers (id, source_id, title, company_name) VALUES (1, 'A', 'A', 'A'), (2, 'B', 'B', 'B'), (3, 'C', 'C', 'C'), (4, 'D', 'D', 'D')"
            )
            conn.execute(
                "INSERT INTO offer_evaluations (offer_id, match_score, sent_via_telegram, sent_at, daily_position) VALUES (1, 50, 1, datetime('now', '-1 day'), 1), (2, 50, 1, datetime('now', '-1 day'), 2), (3, 60, 1, datetime('now'), 1), (4, 60, 1, datetime('now'), 2)"
            )
            conn.commit()

            with patch("src.telegram.handlers.get_connection") as mock_get:
                mock_get.return_value = conn

                from src.telegram.handlers import get_latest_daily_offers
                result = get_latest_daily_offers()

            conn.close()

        assert len(result) == 2


class TestSaveFeedback:
    """Tests para save_feedback()."""

    def test_save_feedback_ok(self):
        """Guarda correctamente con offer_id."""
        with patch("src.telegram.handlers.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_conn.return_value.commit = MagicMock()

            from src.telegram.handlers import save_feedback

            result = save_feedback("f1", "Me gusta esta oferta", offer_id=10)

            assert result is True
            mock_cursor.execute.assert_called_once()
            mock_conn.return_value.commit.assert_called_once()

    def test_save_feedback_dia(self):
        """Guarda /dia con offer_id=None."""
        with patch("src.telegram.handlers.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_conn.return_value.commit = MagicMock()

            from src.telegram.handlers import save_feedback

            result = save_feedback("dia", "Hoy me siento motivado")

            assert result is True
            args = mock_cursor.execute.call_args[0][1]
            assert args[0] is None
            assert args[1] == "dia"


class TestFeedbackProcessor:
    """Tests para feedback_processor.py."""

    def test_feedback_processor_min_threshold(self):
        """Menos de 3 feedbacks → no llama al modelo."""
        with patch("src.pipeline.feedback_processor.get_pending_feedback") as mock_pending:
            mock_pending.return_value = [
                {"id": 1, "feedback_type": "f1", "raw_text": "a"},
                {"id": 2, "feedback_type": "f2", "raw_text": "b"},
            ]

            from src.pipeline.feedback_processor import run

            with patch("src.pipeline.feedback_processor.ollama_call") as mock_ollama:
                result = run()

            mock_ollama.assert_not_called()
            assert result["skipped"] == 2
            assert result["reason"] == "below_threshold"

    def test_feedback_processor_writes_psychology(self):
        """≥3 feedbacks → escribe en user_psychology."""
        with patch("src.pipeline.feedback_processor.get_pending_feedback") as mock_pending:
            mock_pending.return_value = [
                {"id": 1, "feedback_type": "f1", "raw_text": "salario"},
                {"id": 2, "feedback_type": "f2", "raw_text": "horario"},
                {"id": 3, "feedback_type": "dia", "raw_text": "bien"},
            ]

            with patch("src.pipeline.feedback_processor.get_latest_psychology") as mock_psych:
                mock_psych.return_value = None

                mock_response = {
                    "patrones_preferencia": "Le gusta buen salario",
                    "estado_emocional": "Positivo",
                    "red_flags_personales": ["Horario"],
                    "oportunidades_valoradas": ["Salario"],
                    "notas_adicionales": "Nada",
                }

                from src.pipeline.feedback_processor import run

                with patch("src.pipeline.feedback_processor.ollama_call") as mock_ollama:
                    mock_ollama.return_value = mock_response

                    with patch("src.pipeline.feedback_processor.save_psychology") as mock_save:
                        with patch("src.pipeline.feedback_processor.mark_feedback_processed"):
                            result = run()

                assert result["processed"] == 3