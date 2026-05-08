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


class TestPreFiltroRequisitosImposibles:
    """Tests para pre_filtro_requisitos_imposibles(offer, perfil)."""

    def test_no_descarta_oferta_sin_requisitos_imposibles(
        self, sample_offer, sample_perfil_text
    ):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        es_descartable, razon = pre_filtro_requisitos_imposibles(
            sample_offer, sample_perfil_text
        )

        assert es_descartable is False
        assert razon == ""

    def test_descarta_oferta_para_estudiante(
        self, sample_offer_with_impossible_requirements
    ):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        es_descartable, razon = pre_filtro_requisitos_imposibles(
            sample_offer_with_impossible_requirements, ""
        )

        assert es_descartable is True
        assert razon == "No es estudiante de último año"

    def test_descarta_oferta_para_certificado_discapacidad(self):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        offer = {
            "description_clean": "Se requiere certificado de discapacidad",
            "title": "Analista",
        }
        es_descartable, razon = pre_filtro_requisitos_imposibles(offer, "")

        assert es_descartable is True
        assert razon == "No posee certificado de discapacidad"

    def test_descarta_oferta_para_menor_de_edad(self):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        offer = {
            "description_clean": "Se busca ser menor de 25 años",
            "title": "Becario",
        }
        es_descartable, razon = pre_filtro_requisitos_imposibles(offer, "")

        assert es_descartable is True
        assert razon == "No cumple requisito de edad"

    def test_no_descarta_oferta_sin_carnet_cuando_perfil_no_lo_tiene(self):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        offer = {
            "description_clean": "Se requiere carné de conducir. Experiencia mínima 2 años.",
            "title": "Técnico de datos",
        }
        perfil_sin_carnet = "# PERFIL\n\n## Datos base\n\n- **Nombre:** Test\n"
        es_descartable, razon = pre_filtro_requisitos_imposibles(
            offer, perfil_sin_carnet
        )

        assert es_descartable is True
        assert razon == "No tiene carné de conducir"

    def test_no_descarta_oferta_sin_carnet_cuando_perfil_lo_tiene(self):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        offer = {
            "description_clean": "Carné de conducir obligatorio",
            "title": "Técnico",
        }
        perfil_con_carnet = "# PERFIL\n\n## Datos base\n\n- **Nombre:** Test\n## Skills\n\n- Carné de conducir"
        es_descartable, razon = pre_filtro_requisitos_imposibles(
            offer, perfil_con_carnet
        )

        assert es_descartable is False

    def test_case_insensitive(self, sample_offer_with_impossible_requirements):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        offer_case = {
            "description_clean": "Se busca SER estudiante",
            "title": "Becario",
        }
        es_descartable, razon = pre_filtro_requisitos_imposibles(offer_case, "")

        assert es_descartable is True

    def test_requisito_imposible_solo_en_titulo(self):
        from src.pipeline.evaluate import pre_filtro_requisitos_imposibles

        offer = {
            "description_clean": "Análisis de datos con Python y SQL",
            "title": "Se requiere ser estudiante para prácticas",
        }
        es_descartable, razon = pre_filtro_requisitos_imposibles(offer, "")

        assert es_descartable is True
        assert razon == "No es estudiante activo"
