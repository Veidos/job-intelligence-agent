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
    """Tests para CandidateProfile.skills_map desde PERFIL.md."""

    def test_parsea_skills_con_nivel(self, sample_perfil_text):
        from src.utils.candidate_profile import CandidateProfile

        profile = CandidateProfile.from_perfil(sample_perfil_text)
        skills_map = profile.skills_map

        assert len(skills_map) >= 4
        assert "Python" in skills_map
        assert "SQL" in skills_map
        assert "Pandas" in skills_map
        all(lv in ("básico", "intermedio", "avanzado") for lv in skills_map.values())

    def test_devuelve_vacio_cuando_no_hay_skills(self):
        from src.utils.candidate_profile import CandidateProfile

        perfil_sin_skills = "# PERFIL\n\n## Datos base\n\n- **Nombre:** Test"
        profile = CandidateProfile.from_perfil(perfil_sin_skills)

        assert profile.skills_map == {}

    def test_devuelve_vacio_con_seccion_vacia(self):
        from src.utils.candidate_profile import CandidateProfile

        perfil_vacio = "# PERFIL\n\n## Skills técnicas\n\n"
        profile = CandidateProfile.from_perfil(perfil_vacio)

        assert profile.skills_map == {}

    def test_niveles_extraidos_correctamente(self, sample_perfil_text):
        from src.utils.candidate_profile import CandidateProfile

        profile = CandidateProfile.from_perfil(sample_perfil_text)

        assert "Python" in profile.skills_map
        assert profile.skills_map["Python"] == "básico"


class TestLoadGapFromPerfil:
    """Tests para CandidateProfile.employment_gap."""

    def test_parsea_gap_correctamente(self, sample_perfil_text):
        from src.utils.candidate_profile import CandidateProfile

        profile = CandidateProfile.from_perfil(sample_perfil_text)

        assert profile.employment_gap == 2.5

    def test_devuelve_none_cuando_no_hay_gap(self):
        from src.utils.candidate_profile import CandidateProfile

        perfil_sin_gap = "# PERFIL\n\n## Datos base\n\n- **Nombre:** Test"
        profile = CandidateProfile.from_perfil(perfil_sin_gap)

        assert profile.employment_gap is None

    def test_devuelve_none_con_seccion_gap_vacia(self):
        from src.utils.candidate_profile import CandidateProfile

        perfil_vacio = "# PERFIL\n\n## Gap de empleo\n\n"
        profile = CandidateProfile.from_perfil(perfil_vacio)

        assert profile.employment_gap is None

    def test_parsea_gap_decimal(self):
        from src.utils.candidate_profile import CandidateProfile

        perfil = "# PERFIL\n\n## Gap de empleo\n\n- **Años:** 3.7"
        profile = CandidateProfile.from_perfil(perfil)

        assert profile.employment_gap == 3.7
