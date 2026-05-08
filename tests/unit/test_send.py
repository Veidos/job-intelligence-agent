"""Unit tests para telegram/send.py — lógica de formato y feedback."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


class TestFormatOffer:
    """Tests para format_offer(offer, position)."""

    def test_prioritario_con_salary(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["match_score"] = 80
        result = format_offer(offer, 1)

        assert "[1]" in result
        assert "🟢" in result
        assert "Data Analyst Junior" in result
        assert "TechCorp" in result
        assert "Madrid" in result
        assert "Remoto" in result
        assert "24,000" in result or "24000" in result
        assert "Match: 80/100" in result
        assert "🔗" in result

    def test_aplicar_emoji_amarillo(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["match_score"] = 60
        result = format_offer(offer, 2)

        assert "🟡" in result

    def test_expectativas_bajas_emoji_naranja(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["match_score"] = 40
        result = format_offer(offer, 3)

        assert "🟠" in result

    def test_nota_baja_cuando_score_menor_55(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["match_score"] = 40
        offer["recommendation"] = "Con expectativas bajas"
        result = format_offer(offer, 1)

        assert "Incluida por falta de opciones superiores" in result

    def test_sin_nota_cuando_score_mayor_igual_55(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["match_score"] = 60
        offer["recommendation"] = "Aplicar"
        result = format_offer(offer, 1)

        assert "Incluida por falta de opciones superiores" not in result

    def test_url_absoluta(self, sample_offer):
        from src.telegram.send import format_offer

        result = format_offer(sample_offer, 1)

        assert "http" in result

    def test_url_relativa_se_convierte(self):
        from src.telegram.send import format_offer

        offer = {
            "match_score": 40,
            "recommendation": "Aplicar",
            "title": "Test",
            "company_name": "Corp",
            "city": "Madrid",
            "work_mode": "Remoto",
            "url": "/oferta/test",
            "hr_concerns": "[]",
            "interview_prep": "[]",
        }
        result = format_offer(offer, 1)

        assert "https://www.infojobs.net/oferta/test" in result

    def test_concern_mostrado_si_existe(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["hr_concerns"] = json.dumps(["Empresa grande, no recomendado"])
        result = format_offer(offer, 1)

        assert "⚠️" in result
        assert "Empresa grande" in result

    def test_sin_concern_cuando_lista_vacia(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["hr_concerns"] = "[]"
        result = format_offer(offer, 1)

        assert "⚠️" not in result

    def test_interview_prep_mostrado_si_existe(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["interview_prep"] = json.dumps(["Preparar ejemplos de proyectos"])
        result = format_offer(offer, 1)

        assert "🎯" in result
        assert "Preparar ejemplos" in result

    def test_salary_solo_minimo(self):
        from src.telegram.send import format_offer

        offer = {
            "match_score": 40,
            "recommendation": "Aplicar",
            "title": "Test",
            "company_name": "Corp",
            "city": "Madrid",
            "work_mode": "Remoto",
            "salary_min": 20000.0,
            "salary_max": None,
            "url": "https://www.infojobs.net/oferta/test",
            "hr_concerns": "[]",
            "interview_prep": "[]",
        }
        result = format_offer(offer, 1)

        assert "20,000" in result or "20000" in result
        assert "desde" in result

    def test_sin_salary(self):
        from src.telegram.send import format_offer

        offer = {
            "match_score": 40,
            "recommendation": "Aplicar",
            "title": "Test",
            "company_name": "Corp",
            "city": "Madrid",
            "work_mode": "Remoto",
            "salary_min": None,
            "salary_max": None,
            "url": "https://www.infojobs.net/oferta/test",
            "hr_concerns": "[]",
            "interview_prep": "[]",
        }
        result = format_offer(offer, 1)

        assert "salary" not in result.lower() or "|" not in result.split("\n")[1]

    def test_nulo_city(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["city"] = None
        result = format_offer(offer, 1)

        assert "None" in result

    def test_nulo_work_mode(self, sample_offer):
        from src.telegram.send import format_offer

        offer = sample_offer.copy()
        offer["work_mode"] = None
        result = format_offer(offer, 1)

        assert "None" in result


class TestProcessFeedback:
    """Tests para process_feedback(text)."""

    def test_f1_feedback(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/f1 me gusta esta oferta")

        assert result == "Anotado 📝"

    def test_f2_feedback(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/f2 interesante")

        assert result == "Anotado 📝"

    def test_f3_feedback(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/f3 buena oferta")

        assert result == "Anotado 📝"

    def test_f4_f5_feedback(self):
        from src.telegram.send import process_feedback

        assert process_feedback("/f4 texto") == "Anotado 📝"
        assert process_feedback("/f5 texto") == "Anotado 📝"

    def test_dia_feedback(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/dia hoy estoy cansado")

        assert result == "Entendido, lo tengo en cuenta 🧠"

    def test_sin_comando_retorna_vacio(self):
        from src.telegram.send import process_feedback

        result = process_feedback("solo texto sin comando")

        assert result == ""

    def test_comando_sin_espacio(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/f1sin texto")

        assert result == ""

    def test_recorta_espacios(self):
        from src.telegram.send import process_feedback

        result = process_feedback("  /f1   me gusta esta oferta  ")

        assert result == "Anotado 📝"

    def test_dia_sin_espacio_despues(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/diahoy estoy mal")

        assert result == ""

    def test_f1_sin_texto_retorna_empty(self):
        from src.telegram.send import process_feedback

        result = process_feedback("/f1")

        assert result == ""
