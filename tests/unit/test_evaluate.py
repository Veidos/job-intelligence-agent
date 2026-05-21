"""Unit tests para evaluate.py — lógica pura sin dependencias externas."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestClamp:
    """Tests para _clamp(val, lo, hi)."""

    def test_valor_dentro_del_rango(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(5, 0, 10) == 5

    def test_valor_bajo_del_rango(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(-5, 0, 10) == 0

    def test_valor_alto_del_rango(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(15, 0, 10) == 10

    def test_valor_none(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(None, 0, 10) == 0

    def test_valor_float_dentro_del_rango(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(5.7, 0, 10) == 5

    def test_limite_inferior_exacto(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(0, 0, 10) == 0

    def test_limite_superior_exacto(self):
        from src.pipeline.evaluate import _clamp

        assert _clamp(10, 0, 10) == 10


class TestGetRating:
    """Tests para get_rating(score)."""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (80, "Prioritario"),
            (75, "Prioritario"),
            (100, "Prioritario"),
            (60, "Aplicar"),
            (55, "Aplicar"),
            (74, "Aplicar"),
            (40, "Con expectativas bajas"),
            (35, "Con expectativas bajas"),
            (54, "Con expectativas bajas"),
            (30, "No aplicar"),
            (0, "No aplicar"),
            (34, "No aplicar"),
        ],
    )
    def test_rating_labels(self, score, expected):
        from src.pipeline.evaluate import get_rating

        assert get_rating(score) == expected


class TestLoadSkillsFromPerfil:
    """Tests para load_skills_from_perfil(perfil)."""

    def test_parsea_skills_con_nivel(self, sample_perfil_text):
        from src.pipeline.evaluate import load_skills_from_perfil

        skills = load_skills_from_perfil(sample_perfil_text)

        assert len(skills) >= 4
        names = {s["name"] for s in skills}
        assert "Python" in names
        assert "SQL" in names
        assert "Pandas" in names
        for s in skills:
            assert s["level"] in ("básico", "intermedio", "avanzado")

    def test_devuelve_lista_vacia_cuando_no_hay_skills(self):
        from src.pipeline.evaluate import load_skills_from_perfil

        perfil_sin_skills = "# PERFIL\n\n## Datos base\n\n- **Nombre:** Test"
        skills = load_skills_from_perfil(perfil_sin_skills)

        assert skills == []

    def test_devuelve_lista_vacia_con_seccion_vacia(self):
        from src.pipeline.evaluate import load_skills_from_perfil

        perfil_vacio = "# PERFIL\n\n## Skills técnicas\n\n"
        skills = load_skills_from_perfil(perfil_vacio)

        assert skills == []

    def test_niveles_extraidos_correctamente(self, sample_perfil_text):
        from src.pipeline.evaluate import load_skills_from_perfil

        skills = load_skills_from_perfil(sample_perfil_text)

        python_skill = next((s for s in skills if s["name"] == "Python"), None)
        assert python_skill is not None
        assert python_skill["level"] == "básico"


class TestLoadGapFromPerfil:
    """Tests para load_gap_from_perfil(perfil)."""

    def test_parsea_gap_correctamente(self, sample_perfil_text):
        from src.pipeline.evaluate import load_gap_from_perfil

        gap = load_gap_from_perfil(sample_perfil_text)

        assert gap == 2.5

    def test_devuelve_none_cuando_no_hay_gap(self):
        from src.pipeline.evaluate import load_gap_from_perfil

        perfil_sin_gap = "# PERFIL\n\n## Datos base\n\n- **Nombre:** Test"
        gap = load_gap_from_perfil(perfil_sin_gap)

        assert gap is None

    def test_devuelve_none_con_seccion_gap_vacia(self):
        from src.pipeline.evaluate import load_gap_from_perfil

        perfil_vacio = "# PERFIL\n\n## Gap de empleo\n\n"
        gap = load_gap_from_perfil(perfil_vacio)

        assert gap is None

    def test_parsea_gap_decimal(self):
        from src.pipeline.evaluate import load_gap_from_perfil

        perfil = "# PERFIL\n\n## Gap de empleo\n\n- **Años:** 3.7"
        gap = load_gap_from_perfil(perfil)

        assert gap == 3.7


class TestCheckImpossibleRequirements:
    """Tests para check_impossible_requirements(offer, perfil) con ollama_call mockeado."""

    def test_no_descarta_sin_requisitos_imposibles(self, mocker):
        mocker.patch(
            "src.pipeline.evaluate.ollama_call",
            return_value={"descartable": False, "razon": ""},
        )
        from src.pipeline.evaluate import check_impossible_requirements

        result = check_impossible_requirements(
            {"title": "Data Analyst", "description_clean": "Python y SQL"},
            "# PERFIL\n- Python",
        )
        assert result["descartable"] is False
        assert result["razon"] == ""

    def test_descarta_por_estudiante(self, mocker):
        mocker.patch(
            "src.pipeline.evaluate.ollama_call",
            return_value={
                "descartable": True,
                "razon": "La oferta requiere ser estudiante activo y el candidato no lo es",
            },
        )
        from src.pipeline.evaluate import check_impossible_requirements

        result = check_impossible_requirements(
            {
                "title": "Becario",
                "description_clean": "Se busca estudiante de último año",
            },
            "# PERFIL\n- **Nombre:** Test",
        )
        assert result["descartable"] is True
        assert "estudiante" in result["razon"]

    def test_descarta_por_carnet_no_disponible(self, mocker):
        mocker.patch(
            "src.pipeline.evaluate.ollama_call",
            return_value={
                "descartable": True,
                "razon": "El candidato no tiene carné de conducir",
            },
        )
        from src.pipeline.evaluate import check_impossible_requirements

        result = check_impossible_requirements(
            {
                "title": "Técnico",
                "description_clean": "Carné de conducir obligatorio",
            },
            "# PERFIL\n- **Nombre:** Test",
        )
        assert result["descartable"] is True

    def test_maneja_error_ollama_devuelve_false(self, mocker):
        mocker.patch(
            "src.pipeline.evaluate.ollama_call",
            return_value="respuesta inválida",
        )
        from src.pipeline.evaluate import check_impossible_requirements

        result = check_impossible_requirements(
            {"title": "Test", "description_clean": "test"},
            "# PERFIL",
        )
        assert result["descartable"] is False
        assert result["razon"] == ""

    def test_verifica_que_llama_ollama_con_temp_cero(self, mocker):
        mock = mocker.patch("src.pipeline.evaluate.ollama_call")
        from src.pipeline.evaluate import check_impossible_requirements

        check_impossible_requirements(
            {
                "title": "Data Analyst",
                "company_name": "Corp",
                "description_clean": "SQL",
            },
            "# PERFIL\n- Python",
        )
        assert mock.called
        kwargs = mock.call_args[1]
        assert kwargs["temperature"] == 0.0
        assert kwargs["expect_json"] is True
        assert kwargs["model"] == "gemma4:e4b"
