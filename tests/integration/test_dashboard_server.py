"""Tests de integración para el dashboard Flask (server.py).

Verifica que los endpoints REST devuelvan JSON válido con los datos
correctos cuando hay ofertas evaluadas en la DB.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def seed_db(test_engine):
    """Puebla la DB con datos mínimos para testear los endpoints."""
    cur = test_engine.cursor()

    try:
        # Insertar oferta evaluada
        cur.execute(
            """
            INSERT INTO offers (
                source_id, title, company_name, city, work_mode, url,
                description_clean, skills_required, salary_min, salary_max,
                published_at, is_evaluated, is_active, relevance_flag,
                role_normalized
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "DASH-TEST-001",
                "Data Analyst Test",
                "TestCorp",
                "Madrid",
                "Remoto",
                "https://infojobs.net/of-111",
                "Descripción de prueba para tests del dashboard",
                json.dumps({"core": [{"name": "Python"}], "secondary": []}),
                30000,
                40000,
                "2026-06-01",
                1,
                1,
                "core",
                "data_analyst",
            ),
        )
        offer_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Evaluación
        cur.execute(
            """
            INSERT INTO offer_evaluations (
                offer_id, skills_hard_match, experience_match, location_match,
                market_competitiveness, scoring_detail, match_score,
                recommendation, gemma_verdict, hr_concerns, strengths,
                red_flags, interview_prep, model_technical, model_hr,
                apply_block, llm_apply_signal
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer_id,
                45,
                60,
                100,
                15,
                json.dumps({"M_core": 0.6, "M_sec": 0.0, "F_exp": 1.0, "F_fit": 0.7}),
                65,
                "Aplicar",
                "Buena oferta para el perfil",
                json.dumps(["Equipo pequeño"]),
                json.dumps(["Python", "SQL"]),
                json.dumps([]),
                json.dumps(["Preparar preguntas técnicas"]),
                "gemma4:e4b",
                "gemma4:e4b",
                None,
                "yes",
            ),
        )

        # Empresa
        cur.execute(
            "INSERT INTO companies (name, sector, size_range) VALUES (?, ?, ?)",
            ("TestCorp", "Tecnología", "grande"),
        )
        company_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]

        cur.execute(
            "UPDATE offers SET company_id = ? WHERE id = ?", (company_id, offer_id)
        )

        # Aplicación
        cur.execute(
            "INSERT INTO applications (offer_id, status, notes) VALUES (?, ?, ?)",
            (offer_id, "applied", "Aplicado desde test"),
        )

        # Search run
        cur.execute(
            """INSERT INTO search_runs (query_params, offers_fetched, new_offers, evaluated, status, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('{"since_date": "_24_HOURS"}', 5, 2, 1, "ok", 1234),
        )

        # Feedback
        cur.execute(
            "INSERT INTO user_feedback (offer_id, feedback_type, raw_text) VALUES (?, ?, ?)",
            (offer_id, "dashboard", "Interesante oferta"),
        )

        test_engine.commit()
    except Exception:
        test_engine.rollback()
        raise

    yield offer_id

    # Cleanup entre tests
    test_engine.execute("DELETE FROM user_feedback")
    test_engine.execute("DELETE FROM applications")
    test_engine.execute("DELETE FROM search_runs")
    test_engine.execute("DELETE FROM offer_evaluations")
    test_engine.execute("DELETE FROM offers")
    test_engine.execute("DELETE FROM companies")
    test_engine.commit()


@pytest.fixture
def client(test_engine):
    """Cliente de prueba Flask con monkeypatch de get_connection.

    Envuelve test_engine para que close() sea no-op — el server.py
    cierra la conexión tras cada request y no queremos cerrar la
    conexión session-scoped.
    """
    from src.dashboard.server import app

    class _NoCloseConn:
        def __init__(self, engine):
            self._conn = engine
            self._row_factory = engine.row_factory

        @property
        def row_factory(self):
            return self._row_factory

        @row_factory.setter
        def row_factory(self, val):
            self._row_factory = val
            self._conn.row_factory = val

        def cursor(self):
            return self._conn.cursor()

        def execute(self, *args, **kwargs):
            return self._conn.execute(*args, **kwargs)

        def commit(self):
            self._conn.commit()

        def close(self):
            pass

    def _mock_get_connection():
        return _NoCloseConn(test_engine)

    with patch("src.dashboard.server.get_connection", _mock_get_connection):
        with app.test_client() as c:
            yield c


class TestDashboardAPI:
    """Tests para los endpoints REST del dashboard."""

    def test_api_stats(self, client, seed_db):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_offers"] == 1
        assert data["evaluated"] == 1
        assert data["classified"] == 1
        assert data["companies"] == 1
        assert data["applications"] == 1
        assert data["feedbacks"] == 1
        assert data["avg_score"] == 65.0
        assert data["max_score"] == 65
        assert len(data["rec_counts"]) > 0

    def test_api_offers(self, client, seed_db):
        resp = client.get("/api/offers")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "Data Analyst Test"
        assert data[0]["match_score"] == 65
        assert data[0]["recommendation"] == "Aplicar"
        assert data[0]["salary_display"] == "30k–40k"

    def test_api_offers_with_filters(self, client, seed_db):
        resp = client.get("/api/offers?min_score=50&rec=Aplicar&limit=5")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["match_score"] == 65

        resp_empty = client.get("/api/offers?min_score=80")
        assert resp_empty.status_code == 200
        assert len(resp_empty.get_json()) == 0

    def test_api_offers_with_search(self, client, seed_db):
        resp = client.get("/api/offers?search=Data+Analyst")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1

        resp_no = client.get("/api/offers?search=NoExiste")
        assert resp_no.status_code == 200
        assert len(resp_no.get_json()) == 0

    def test_api_offer_detail(self, client, seed_db):
        offer_id = seed_db
        resp = client.get(f"/api/offers/{offer_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["offer"]["title"] == "Data Analyst Test"
        assert len(data["feedback"]) == 1
        assert data["application"]["status"] == "applied"

    def test_api_offer_detail_404(self, client):
        resp = client.get("/api/offers/99999")
        assert resp.status_code == 404

    def test_api_companies(self, client, seed_db):
        resp = client.get("/api/companies")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "TestCorp"
        assert data[0]["offer_count"] == 1
        assert data[0]["avg_score"] == 65.0

    def test_api_applications_get(self, client, seed_db):
        resp = client.get("/api/applications")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["status"] == "applied"
        assert data[0]["offer_title"] == "Data Analyst Test"

    def test_api_applications_post_create(self, client, seed_db):
        resp = client.post(
            "/api/applications",
            json={
                "offer_id": seed_db,
                "status": "interviewing",
                "notes": "Entrevista programada",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        resp_get = client.get("/api/applications")
        apps = resp_get.get_json()
        matching = [a for a in apps if a["offer_id"] == seed_db]
        assert len(matching) == 1
        assert matching[0]["status"] == "interviewing"

    def test_api_applications_delete(self, client, seed_db):
        resp = client.get("/api/applications")
        app_id = resp.get_json()[0]["id"]

        resp_del = client.delete(f"/api/applications/{app_id}")
        assert resp_del.status_code == 200

        resp_get = client.get("/api/applications")
        assert len(resp_get.get_json()) == 0

    def test_api_feedback_get(self, client, seed_db):
        resp = client.get("/api/feedback")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["raw_text"] == "Interesante oferta"

    def test_api_feedback_post(self, client, seed_db):
        resp = client.post(
            "/api/feedback",
            json={"offer_id": seed_db, "raw_text": "Me gusta esta oferta"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

        resp_get = client.get("/api/feedback")
        feedbacks = resp_get.get_json()
        matching = [
            f
            for f in feedbacks
            if f["offer_id"] == seed_db and "Me gusta" in f["raw_text"]
        ]
        assert len(matching) == 1

    def test_api_feedback_post_missing_fields(self, client):
        resp = client.post("/api/feedback", json={})
        assert resp.status_code == 400

    def test_api_runs(self, client, seed_db):
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["status"] == "ok"
        assert data[0]["offers_fetched"] == 5

    def test_api_runs_empty(self, client):
        """Sin datos seed_db, runs debe devolver lista vacía."""
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_index_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/html")

    def test_static_files(self, client):
        resp = client.get("/static/app.js")
        assert resp.status_code == 200

        resp_css = client.get("/static/style.css")
        assert resp_css.status_code == 200

    def test_favicon_no_content(self, client):
        resp = client.get("/favicon.ico")
        assert resp.status_code == 204
