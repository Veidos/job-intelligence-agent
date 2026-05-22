"""Unit tests para funciones puras de role_classifier.py."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.role_classifier import GAP_HIERARCHY, GAP_TO_FLAG, resolve_gap_type


class TestResolveGapType:
    def test_vacio_retorna_none(self):
        assert resolve_gap_type([]) == "none"

    def test_unico_elemento(self):
        assert resolve_gap_type(["herramienta"]) == "herramienta"
        assert resolve_gap_type(["dominio"]) == "dominio"
        assert resolve_gap_type(["seniority"]) == "seniority"
        assert resolve_gap_type(["estructural"]) == "estructural"
        assert resolve_gap_type(["none"]) == "none"

    def test_jerarquia_seniority_domina_herramienta(self):
        assert resolve_gap_type(["herramienta", "seniority"]) == "seniority"

    def test_jerarquia_estructural_domina_todo(self):
        assert resolve_gap_type(["none", "dominio", "estructural"]) == "estructural"

    def test_jerarquia_completa(self):
        assert (
            resolve_gap_type(["herramienta", "dominio", "seniority", "estructural"])
            == "estructural"
        )

    def test_ignora_tipos_desconocidos(self):
        assert resolve_gap_type(["unknown", "none"]) == "none"

    def test_estructural_mas_herramienta(self):
        assert resolve_gap_type(["herramienta", "estructural"]) == "estructural"

    def test_dominio_mas_herramienta(self):
        assert resolve_gap_type(["herramienta", "dominio"]) == "dominio"


class TestGAP_TO_FLAG:
    def test_todas_las_claves_tienen_flag(self):
        for gap in GAP_HIERARCHY:
            assert gap in GAP_TO_FLAG, f"Falta mapping para gap_type={gap}"

    def test_todos_los_flags_son_validos(self):
        valid_flags = {"core", "adjacent", "stretch", "temporal"}
        for gap, flag in GAP_TO_FLAG.items():
            assert flag in valid_flags, f"Flag inválido {flag} para gap={gap}"

    def test_mapping_correcto(self):
        assert GAP_TO_FLAG["none"] == "core"
        assert GAP_TO_FLAG["herramienta"] == "adjacent"
        assert GAP_TO_FLAG["dominio"] == "adjacent"
        assert GAP_TO_FLAG["seniority"] == "stretch"
        assert GAP_TO_FLAG["estructural"] == "temporal"

    def test_fallback_default(self):
        assert GAP_TO_FLAG.get("unknown", "stretch") == "stretch"
