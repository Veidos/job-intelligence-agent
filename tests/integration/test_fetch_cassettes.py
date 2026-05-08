"""Integration tests para fetch.py extract_fields_with_qwen() usando cassettes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.ollama import CASSETTES  # noqa: E402


class TestExtractFieldsWithQwen:
    """Tests para extract_fields_with_qwen() con cassettes."""

    def test_extrae_campos_de_oferta_junior(self):
        from src.pipeline.fetch import extract_fields_with_qwen

        mock_response = CASSETTES["extract_fields_junior"]

        item = {
            "offer": {
                "code": "TEST-001",
                "title": "Junior Data Analyst",
                "description": "<p>HTML description with <b>bold</b> tags</p>",
            }
        }

        with patch("src.pipeline.fetch.ollama_call") as mock:
            mock.return_value = mock_response
            result = extract_fields_with_qwen(item)

        assert result["skills_required"] == [
            "Python",
            "SQL",
            "Pandas",
            "Excel",
            "Power BI (valorable)",
        ]
        assert result["experience_min"] == 0
        assert result["education_level"] == "Grado o similar en STEM"
        assert result["salary_min"] == 24000
        assert result["salary_max"] == 32000

    def test_extrae_campos_de_oferta_senior(self):
        from src.pipeline.fetch import extract_fields_with_qwen

        mock_response = CASSETTES["extract_fields_senior"]

        item = {
            "offer": {
                "code": "TEST-002",
                "title": "Senior Data Scientist",
                "description": "Long senior description",
            }
        }

        with patch("src.pipeline.fetch.ollama_call") as mock:
            mock.return_value = mock_response
            result = extract_fields_with_qwen(item)

        assert result["experience_min"] == 4
        assert "PyTorch" in result["skills_required"]
        assert "MLOps" in result["skills_required"]
        assert result["salary_min"] == 50000
        assert result["salary_max"] == 70000

    def test_devuelve_dict_vacio_si_ollama_falla(self):
        from src.pipeline.fetch import extract_fields_with_qwen

        item = {
            "offer": {
                "code": "TEST-003",
                "title": "Data Analyst",
                "description": "Description",
            }
        }

        with patch("src.pipeline.fetch.ollama_call") as mock:
            mock.side_effect = Exception("Ollama unavailable")
            result = extract_fields_with_qwen(item)

        assert result == {}

    def test_devuelve_dict_vacio_si_respuesta_no_es_dict(self):
        from src.pipeline.fetch import extract_fields_with_qwen

        item = {
            "offer": {
                "code": "TEST-004",
                "title": "Data Analyst",
                "description": "Description",
            }
        }

        with patch("src.pipeline.fetch.ollama_call") as mock:
            mock.return_value = "这不是 JSON"
            result = extract_fields_with_qwen(item)

        assert result == {}

    def test_usa_modelo_qwen_en_llamada(self):
        from src.pipeline.fetch import extract_fields_with_qwen

        mock_response = CASSETTES["extract_fields_junior"]
        item = {
            "offer": {
                "code": "TEST-005",
                "title": "Data Analyst",
                "description": "Description",
            }
        }

        with patch("src.pipeline.fetch.ollama_call") as mock:
            mock.return_value = mock_response
            extract_fields_with_qwen(item)

        call_args = mock.call_args
        assert "qwen2.5" in call_args[1]["model"]

    def test_pasa_item_completo_en_prompt(self):
        from src.pipeline.fetch import extract_fields_with_qwen

        mock_response = CASSETTES["extract_fields_junior"]
        item = {
            "offer": {
                "code": "TEST-006",
                "title": "Full Stack Data Analyst",
                "city": "Madrid",
                "companyName": "TechCorp",
                "description": "Complete job description here",
            }
        }

        with patch("src.pipeline.fetch.ollama_call") as mock:
            mock.return_value = mock_response
            extract_fields_with_qwen(item)

        call_args = mock.call_args
        # ollama_call(model, prompt, ...) → model en args[0], prompt en args[1] o kwargs["prompt"]
        prompt = (
            call_args.kwargs.get("prompt")
            if call_args.kwargs
            else (call_args[0][1] if len(call_args[0]) > 1 else "")
        )
        assert prompt, "Prompt should not be empty"
        assert "TEST-006" in prompt
        assert "TechCorp" in prompt
        assert "Madrid" in prompt
