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
    """Tests para get_rating(score) con float 0.0-1.0."""

    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.80, "Prioritario"),
            (0.75, "Prioritario"),
            (1.00, "Prioritario"),
            (0.60, "Aplicar"),
            (0.55, "Aplicar"),
            (0.65, "Aplicar"),
            (0.40, "Con expectativas bajas"),
            (0.35, "Con expectativas bajas"),
            (0.50, "Con expectativas bajas"),
            (0.30, "No aplicar"),
            (0.00, "No aplicar"),
            (0.34, "No aplicar"),
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
