"""Tests de grammar constraints JSON vía Ollama `format` (ADR-024)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils import llm_schemas
from src.utils.ollama_client import _call_ollama_raw, ollama_call


def _capture(**kwargs) -> tuple[dict, str]:
    """Ejecuta _call_ollama_raw con requests.post simulado.

    Returns:
        (payload_enviado, respuesta_cruda)
    """
    fake = {"response": '{"ok": true}'}
    with patch("src.utils.ollama_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=lambda: None,
            json=lambda: fake,
        )
        result = _call_ollama_raw("gemma4:e4b", "p", **kwargs)
        sent = mock_post.call_args.kwargs["json"]
    return sent, result


class TestSchemas:
    """Estructura de los schemas: estricta en tipos/enums, permisiva en contenido."""

    def test_son_objetos_json_schema_validos(self):
        for schema in (
            llm_schemas.TECHNICAL_SCHEMA,
            llm_schemas.HR_SCHEMA,
            llm_schemas.FINAL_SCHEMA,
        ):
            assert schema["type"] == "object"
            assert isinstance(schema["properties"], dict)
            assert len(schema["required"]) >= 1

    def test_arrays_sin_minitems(self):
        """Regla de diseño: arrays vacíos permitidos — no forzar relleno."""
        hr = llm_schemas.HR_SCHEMA["properties"]
        for key in ("strengths", "red_flags", "hr_concerns", "interview_prep"):
            assert "minItems" not in hr[key], f"{key} no debe tener minItems"

    def test_enums_criticos_hr(self):
        hr = llm_schemas.HR_SCHEMA["properties"]
        assert hr["apply_signal"]["enum"] == ["yes", "no", "maybe"]
        assert hr["gap_severity"]["enum"] == ["low", "medium", "high"]
        assert hr["environment_compatibility"]["enum"] == ["alta", "media", "baja"]

    def test_campos_anulables_con_null_real(self):
        final = llm_schemas.FINAL_SCHEMA["properties"]
        assert "null" in final["relevance_corrected"]["type"]
        assert "null" in final["apply_block"]["type"]
        skill_level = llm_schemas.SKILL_PRESENT_ITEM["properties"]["candidate_level"]
        assert "null" in skill_level["type"]

    def test_reasoning_obligatorio_en_tecnico(self):
        """Regla del proyecto: gemma4 nunca scores sin razonamiento."""
        assert "reasoning" in llm_schemas.TECHNICAL_SCHEMA["required"]
        assert "verdict" in llm_schemas.HR_SCHEMA["required"]
        assert "relevance_reasoning" in llm_schemas.FINAL_SCHEMA["required"]

    def test_context_fit_es_number(self):
        assert llm_schemas.HR_SCHEMA["properties"]["context_fit"]["type"] == "number"


class TestPayloadFormat:
    """El parámetro json_schema se traduce a `format` en el payload de Ollama."""

    def test_format_presente_cuando_hay_schema(self):
        sent, result = _capture(json_schema={"type": "object"})
        assert result == '{"ok": true}'
        assert sent["format"] == {"type": "object"}
        assert sent["stream"] is False

    def test_format_ausente_por_defecto(self):
        sent, _ = _capture()
        assert "format" not in sent

    def test_ollama_call_reenvia_schema_al_raw(self):
        with patch("src.utils.ollama_client._call_ollama_raw") as mock_raw:
            mock_raw.return_value = '{"x": 1}'
            ollama_call(
                model="gemma4:e4b",
                prompt="p",
                expect_json=True,
                json_schema={"type": "object"},
            )
            assert mock_raw.call_args.kwargs.get("json_schema") == {"type": "object"}
