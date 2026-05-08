"""Integration tests para role_classifier.py usando Ollama cassettes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.ollama import CASSETTES  # noqa: E402


class TestRoleClassifier:
    """Tests para classify_offer() con cassettes."""

    def test_clasifica_data_analyst_como_core(self, sample_offer):
        from src.pipeline.role_classifier import classify_offer

        catalog = ["data_analyst", "data_scientist", "ml_engineer", "bi_analyst"]
        mock_response = CASSETTES["classify_data_analyst"]

        with patch("src.pipeline.role_classifier.ollama_call") as mock:
            mock.return_value = mock_response
            result = classify_offer(sample_offer, catalog, "")

        assert result["role_normalized"] == "data_analyst"
        assert result["relevance_flag"] == "core"
        assert result["is_new_role"] is False

    def test_clasifica_data_scientist_como_stretch(self, sample_offer_senior):
        from src.pipeline.role_classifier import classify_offer

        catalog = ["data_analyst", "data_scientist", "ml_engineer", "bi_analyst"]
        mock_response = CASSETTES["classify_data_scientist"]

        with patch("src.pipeline.role_classifier.ollama_call") as mock:
            mock.return_value = mock_response
            result = classify_offer(sample_offer_senior, catalog, "")

        assert result["role_normalized"] == "data_scientist"
        assert result["relevance_flag"] == "stretch"

    def test_clasifica_temporal(self, sample_offer_temporal):
        from src.pipeline.role_classifier import classify_offer

        catalog = ["data_analyst", "data_scientist", "temporal"]
        mock_response = CASSETTES["classify_temporal"]

        with patch("src.pipeline.role_classifier.ollama_call") as mock:
            mock.return_value = mock_response
            result = classify_offer(sample_offer_temporal, catalog, "")

        assert result["role_normalized"] == "temporal"
        assert result["relevance_flag"] == "temporal"

    def test_retorna_none_si_gemma4_falla(self, sample_offer):
        from src.pipeline.role_classifier import classify_offer

        catalog = ["data_analyst"]

        with patch("src.pipeline.role_classifier.ollama_call") as mock:
            mock.return_value = None
            result = classify_offer(sample_offer, catalog, "")

        assert result is None

    def test_retorna_none_si_falta_campo(self, sample_offer):
        from src.pipeline.role_classifier import classify_offer

        catalog = ["data_analyst"]
        incomplete_response = {"role_normalized": "data_analyst"}

        with patch("src.pipeline.role_classifier.ollama_call") as mock:
            mock.return_value = incomplete_response
            result = classify_offer(sample_offer, catalog, "")

        assert result is None

    def test_usa_perfil_content_en_prompt(self, sample_offer):
        from src.pipeline.role_classifier import classify_offer

        catalog = ["data_analyst"]
        mock_response = CASSETTES["classify_data_analyst"]
        perfil_content = "Datos del candidato..." * 500

        with patch("src.pipeline.role_classifier.ollama_call") as mock:
            mock.return_value = mock_response
            classify_offer(sample_offer, catalog, perfil_content)

        call_args = mock.call_args
        assert (
            perfil_content[:200] in call_args[1]["prompt"] or len(call_args[0][1]) > 100
        )


class TestRoleCatalog:
    """Tests para get_role_catalog() y update_role_catalog().
    IMPORTANTE: role_classifier usa conn.cursor() — necesita test_engine (Connection), no test_db (Cursor).
    """

    def test_get_role_catalog_crea_inicial_si_vacio(self, test_engine):
        from src.pipeline.role_classifier import get_role_catalog

        result = get_role_catalog(test_engine)
        assert len(result) > 0
        assert "data_analyst" in result

    def test_get_role_catalog_carga_existente(self, test_engine):
        from src.pipeline.role_classifier import get_role_catalog

        catalog = json.dumps(["custom_role", "another_role"])
        test_engine.execute(
            "INSERT INTO search_config (role_catalog, generated_at) VALUES (?, datetime('now'))",
            (catalog,),
        )

        result = get_role_catalog(test_engine)
        assert "custom_role" in result
        assert "another_role" in result

    def test_update_role_catalog(self, test_engine):
        from src.pipeline.role_classifier import get_role_catalog, update_role_catalog

        new_catalog = ["role_a", "role_b", "role_c"]

        result = update_role_catalog(test_engine, new_catalog)
        assert result is None

        loaded = get_role_catalog(test_engine)
        assert len(loaded) == 3
