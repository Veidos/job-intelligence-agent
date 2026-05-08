"""
Fixtures compartidas para todos los tests del proyecto.

Fixtures DB:
- test_engine: session-scoped, sqlite:///:memory:, aplica schema.sql una vez
- test_db: function-scoped, transacción → rollback automático
- test_cursor: cursor sqlite3 directo (para queries raw)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

SCHEMA_PATH = PROJECT_ROOT / "src" / "db" / "schema.sql"


@pytest.fixture(scope="session")
def schema_sql() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def test_engine(schema_sql):
    import tempfile

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()

    engine = sqlite3.connect(db_path, check_same_thread=False)
    yield engine

    engine.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def test_db(test_engine):
    cursor = test_engine.cursor()
    yield cursor
    test_engine.rollback()
    test_engine.execute("DELETE FROM offer_evaluations")
    test_engine.execute("DELETE FROM offers")
    test_engine.execute("DELETE FROM search_config")
    test_engine.commit()


@pytest.fixture(scope="function")
def test_conn(test_engine):
    """Wrapper de conexión compatible con save_evaluation (usa conn.cursor())."""

    class ConnWrapper:
        def __init__(self, conn):
            self._conn = conn

        def cursor(self):
            return self._conn.cursor()

        def commit(self):
            pass

        def close(self):
            pass

    wrapper = ConnWrapper(test_engine)
    yield wrapper


@pytest.fixture(scope="session")
def sample_perfil_text() -> str:
    return """# PERFIL DEL CANDIDATO

## Datos base

- **Nombre:** Test Candidate
- **Ubicación actual:** Madrid, Spain

## Skills técnicas

- **Python (básico)**: Bootcamp Data Science 2023
- **SQL (básico)**: Bootcamp Data Science 2023
- **Pandas (básico)**: Bootcamp IE University
- **Scikit-learn (básico)**: Bootcamp IE University

## Gap de empleo

- **Años:** 2.5
- **Último trabajo:** Data Analyst @ TestCorp (Jan 2022 - Sep 2022)

## Educación

- **Data Science Bootcamp** — IE University (2023)

## Experiencia

### Data Analyst @ TestCorp
**Duración:** Jan 2022 - Sep 2022
**Descripción:** Análisis de datos con Python y SQL

### Junior Developer @ AnotherCorp
**Duración:** Jun 2021 - Dec 2021
**Descripción:** Desarrollo backend básico

## Idiomas

- Spanish (Native)
- English (Advanced)

## Preferencias laborales

- **Modalidad preferida:** remoto
- **Ubicación preferida:** Madrid, Spain
- **Condiciones de mudanza:** Solo si pagan reubicación

## Personal concerns

Sin información adicional

## Entorno preferido / a evitar

**Preferencias:**
- Industrial
- Tecnología
"""


@pytest.fixture
def sample_offer() -> dict[str, Any]:
    return {
        "id": 1,
        "title": "Data Analyst Junior",
        "company_name": "TechCorp",
        "city": "Madrid",
        "work_mode": "Remoto",
        "salary_min": 24000.0,
        "salary_max": 32000.0,
        "url": "https://www.infojobs.net/oferta/test",
        "description_clean": "Buscamos Data Analyst con Python y SQL. Se requiere experiencia de 1 año.",
        "skills_required": json.dumps(["Python", "SQL", "Pandas"]),
        "experience_min": 1,
        "relevance_flag": "core",
        "role_normalized": "data_analyst",
        "match_score": 65,
        "recommendation": "Aplicar",
        "hr_concerns": json.dumps([]),
        "interview_prep": json.dumps([]),
    }


@pytest.fixture
def sample_offer_senior() -> dict[str, Any]:
    return {
        "id": 2,
        "title": "Senior Data Scientist",
        "company_name": "MegaCorp",
        "city": "Barcelona",
        "work_mode": "Híbrido",
        "salary_min": 50000.0,
        "salary_max": 70000.0,
        "url": "https://www.infojobs.net/oferta/test2",
        "description_clean": (
            "Buscamos Senior Data Scientist con experiencia de 4+ años en ML avanzado, "
            "Deep Learning, MLOps y despliegues en producción. PhD valorable."
        ),
        "skills_required": json.dumps(
            ["Python", "PyTorch", "MLOps", "Kubernetes", "PhD"]
        ),
        "experience_min": 4,
        "relevance_flag": "stretch",
        "role_normalized": "data_scientist",
    }


@pytest.fixture
def sample_offer_no_exp() -> dict[str, Any]:
    return {
        "id": 3,
        "title": "Junior Data Analyst",
        "company_name": "StartupXYZ",
        "city": "Valencia",
        "work_mode": "Remoto",
        "salary_min": 18000.0,
        "salary_max": 24000.0,
        "url": "https://www.infojobs.net/oferta/test3",
        "description_clean": (
            "Buscamos Junior Data Analyst sin experiencia previa. "
            "Formación en Data Science valorable. Python y SQL básico."
        ),
        "skills_required": json.dumps(["Python", "SQL"]),
        "experience_min": 0,
        "relevance_flag": "core",
        "role_normalized": "data_analyst",
    }


@pytest.fixture
def sample_offer_temporal() -> dict[str, Any]:
    return {
        "id": 4,
        "title": "Operador de datos",
        "company_name": "TempCorp",
        "city": "Sevilla",
        "work_mode": "Presencial",
        "salary_min": 15000.0,
        "salary_max": 18000.0,
        "url": "https://www.infojobs.net/oferta/test4",
        "description_clean": (
            "Trabajo temporal de录入 de datos. No se requiere experiencia."
        ),
        "skills_required": json.dumps(["Excel", "SQL básico"]),
        "experience_min": 0,
        "relevance_flag": "temporal",
        "role_normalized": "temporal",
    }


@pytest.fixture
def sample_offer_with_impossible_requirements() -> dict[str, Any]:
    return {
        "id": 5,
        "title": "Becario Data Analyst",
        "company_name": "InternCorp",
        "city": "Madrid",
        "work_mode": "Presencial",
        "salary_min": None,
        "salary_max": None,
        "url": "https://www.infojobs.net/oferta/test5",
        "description_clean": (
            "Se busca estudiante de último año de carrera para prácticas. "
            "Firma de convenio de prácticas obligatoria. Carné de conducir requerido."
        ),
        "skills_required": json.dumps(["Python", "SQL"]),
        "experience_min": 0,
        "relevance_flag": "stretch",
        "role_normalized": "data_analyst",
    }


@pytest.fixture
def ollama_mock():
    """Mock configurable para ollama_call."""
    return MagicMock()
