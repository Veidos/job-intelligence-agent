"""Unit tests para _merge_scraper_skills_into_llm en fetch.py."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


def _merge_scraper_skills_into_llm(detail_skills, llm_skills):
    """Copia inline para test — importar directamente."""
    from src.pipeline.fetch import _merge_scraper_skills_into_llm as fn
    return fn(detail_skills, llm_skills)


class TestMergeScraperSkillsIntoLLM:

    def test_caso1_entity_framework_en_secondary_vuelve_a_core(self):
        """Skill del scraper en secondary LLM → vuelve a core con nombre original."""
        scraper = ["Entity Framework"]
        llm = {"core": [{"name": "Python"}], "secondary": [{"name": "EntityFramework"}]}
        result = _merge_scraper_skills_into_llm(scraper, llm)

        core_names = [s["name"] for s in result["core"]]
        sec_names = [s["name"] for s in result["secondary"]]

        assert "Entity Framework" in core_names  # nombre del scraper
        assert "EntityFramework" not in core_names  # versión LLM no aparece
        assert "Python" in core_names
        assert sec_names == []

    def test_caso2_skill_scraper_ausente_en_llm_se_anade(self):
        """Skill del scraper que el LLM omitió → se añade a core."""
        scraper = ["Docker"]
        llm = {"core": [{"name": "Python"}], "secondary": [{"name": "Git"}]}
        result = _merge_scraper_skills_into_llm(scraper, llm)

        core_names = [s["name"] for s in result["core"]]
        sec_names = [s["name"] for s in result["secondary"]]

        assert "Python" in core_names
        assert "Docker" in core_names
        assert sec_names == ["Git"]

    def test_caso3_secondary_sin_match_se_conserva(self):
        """Secondary del LLM sin coincidencia en scraper → se conserva."""
        scraper = ["Python"]
        llm = {"core": [{"name": "Python"}], "secondary": [{"name": "Tableau"}]}
        result = _merge_scraper_skills_into_llm(scraper, llm)

        core_names = [s["name"] for s in result["core"]]
        sec_names = [s["name"] for s in result["secondary"]]

        assert "Python" in core_names
        assert "Tableau" in sec_names
        assert len(core_names) == 1

    def test_caso4_scraper_vacio_respeta_llm(self):
        """Scraper vacío → no se modifica lo que devuelve el LLM."""
        scraper = []
        llm = {"core": [{"name": "Python"}], "secondary": [{"name": "Git"}]}
        result = _merge_scraper_skills_into_llm(scraper, llm)

        core_names = [s["name"] for s in result["core"]]
        sec_names = [s["name"] for s in result["secondary"]]

        assert core_names == ["Python"]
        assert sec_names == ["Git"]

    def test_caso5_llm_vacio_fallback_a_scraper(self):
        """LLM devuelve vacío → fallback a scraper en core."""
        scraper = ["Python", "SQL"]
        llm = {"core": [], "secondary": []}
        result = _merge_scraper_skills_into_llm(scraper, llm)

        core_names = [s["name"] for s in result["core"]]
        sec_names = [s["name"] for s in result["secondary"]]

        assert "Python" in core_names
        assert "SQL" in core_names
        assert sec_names == []

    def test_caso6_normalizacion_powerbi(self):
        """Normalización: 'Power BI' vs 'PowerBI' vs 'power-bi'."""
        scraper = ["Power BI"]
        llm = {"core": [], "secondary": [{"name": "PowerBI"}]}
        result = _merge_scraper_skills_into_llm(scraper, llm)

        core_names = [s["name"] for s in result["core"]]
        sec_names = [s["name"] for s in result["secondary"]]

        assert "Power BI" in core_names  # nombre original del scraper
        assert "PowerBI" not in core_names
        assert sec_names == []
