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


class TestExperienceScoring:
    def test_none_means_unknown_but_zero_means_no_requirement(self):
        from src.pipeline.evaluate import compute_experience_score

        assert compute_experience_score(None, 4.0) is None
        assert compute_experience_score(0, 4.0) == 1.0

    @pytest.mark.parametrize(
        ("has_secondary", "has_exp", "expected"),
        [
            (True, True, {"W_CORE": 0.45, "W_SEC": 0.15, "W_EXP": 0.25, "W_FIT": 0.15}),
            (False, True, {"W_CORE": 0.60, "W_SEC": 0.0, "W_EXP": 0.25, "W_FIT": 0.15}),
            (True, False, {"W_CORE": 0.60, "W_SEC": 0.20, "W_EXP": 0.0, "W_FIT": 0.20}),
            (False, False, {"W_CORE": 0.80, "W_SEC": 0.0, "W_EXP": 0.0, "W_FIT": 0.20}),
        ],
    )
    def test_compute_effective_weights(self, has_secondary, has_exp, expected):
        from src.pipeline.evaluate import compute_effective_weights

        weights = compute_effective_weights(has_secondary, has_exp)
        assert weights == expected
        assert sum(weights.values()) == pytest.approx(1.0)


class TestExperienceScoringPersistence:
    def test_none_experience_is_stored_as_sql_null_and_marked_redistributed(self):
        import json

        from src.pipeline.evaluate import _build_evaluation_params, compute_effective_weights

        params = _build_evaluation_params(
            offer_id=1,
            hr={},
            final=None,
            skill_detail={"core": [], "secondary": []},
            M_core=0.5,
            M_sec=0.0,
            F_exp=None,
            F_fit=0.75,
            location_match=0.5,
            final_score=0.55,
            recommendation="Aplicar",
            processing_ms=1,
            effective_weights=compute_effective_weights(False, False),
        )

        assert params[3] is None
        details = json.loads(params[6])
        assert details["F_exp"] is None
        assert details["exp_redistributed"] is True
        assert details["weights"]["W_CORE"] == 0.8
        assert details["weights"]["W_FIT"] == 0.2
