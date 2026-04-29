#!/bin/bash
# DEPLOY FASE 1 — Job Intelligence Agent
# Ejecutar desde: ~/proyectos/job-intelligence-agent/
# Con el venv activo: source .venv/bin/activate

set -e
PROJECT="$HOME/proyectos/job-intelligence-agent"
cd "$PROJECT"

echo "=== PASO 1: Directorios ==="
mkdir -p src/db src/utils src/pipeline src/onboarding src/intelligence src/company src/telegram
mkdir -p data logs tests assets
touch logs/.gitkeep data/.gitkeep

echo "=== PASO 2: __init__.py ==="
for pkg in src src/db src/utils src/pipeline src/onboarding src/intelligence src/company src/telegram tests; do
    touch "$pkg/__init__.py"
    echo "  creado $pkg/__init__.py"
done

echo "=== PASO 3: .gitignore ==="
cat > .gitignore << 'EOF'
.env
.venv/
data/
logs/
PERFIL.md
__pycache__/
*.pyc
*.pyo
.ruff_cache/
EOF

echo "=== PASO 4: .env.example ==="
cat > .env.example << 'EOF'
# Copiar a .env y rellenar con valores reales — NUNCA commitear .env
INFOJOBS_CLIENT_ID=
INFOJOBS_CLIENT_SECRET=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DB_PATH=data/jobs.db
LOG_PATH=logs/pipeline.log
PERFIL_PATH=PERFIL.md
EOF

echo "=== PASO 5: requirements.txt ==="
cat > requirements.txt << 'EOF'
# Job Intelligence Agent
requests==2.32.3
sqlalchemy==2.0.35
python-dotenv==1.0.1
python-telegram-bot==21.6
pypdf==4.3.1
tenacity==9.0.0
pydantic==2.9.2
ruff==0.6.9
EOF

echo "=== PASO 6: schema.sql (companies y cv_versions antes de sus FKs) ==="
cat > src/db/schema.sql << 'EOF'
-- Job Intelligence Agent — esquema completo
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- companies ANTES de offers (FK dependency)
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    infojobs_company_id TEXT UNIQUE,
    name TEXT NOT NULL,
    sector TEXT,
    size_range TEXT,
    rating_overall REAL,
    rating_worklife REAL,
    rating_culture REAL,
    rating_growth REAL,
    reviews_count INTEGER DEFAULT 0,
    reviews_sample TEXT,
    avg_inscriptions INTEGER,
    offers_published_30d INTEGER,
    response_rate_signal TEXT DEFAULT 'desconocida',
    first_seen_at DATETIME NOT NULL DEFAULT (datetime('now')),
    last_updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);

-- cv_versions ANTES de candidate_profile (FK dependency)
CREATE TABLE IF NOT EXISTS cv_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    filename TEXT,
    uploaded_at DATETIME NOT NULL DEFAULT (datetime('now')),
    content_parsed TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'infojobs',
    url TEXT,
    title TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    province TEXT,
    city TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_period TEXT,
    contract_type TEXT,
    work_mode TEXT,
    experience_min INTEGER,
    experience_max INTEGER,
    education_level TEXT,
    skills_required TEXT,
    description_raw TEXT,
    description_clean TEXT,
    applications_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    published_at DATETIME,
    expires_at DATETIME,
    fetched_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1,
    is_evaluated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_offers_source_id ON offers(source_id);
CREATE INDEX IF NOT EXISTS idx_offers_fetched_at ON offers(fetched_at);
CREATE INDEX IF NOT EXISTS idx_offers_is_active ON offers(is_active);

CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL DEFAULT '1.0',
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1,
    full_name TEXT,
    location_current TEXT,
    skills_technical TEXT,
    education TEXT,
    experience TEXT,
    languages TEXT,
    projects TEXT,
    employment_gap_years REAL,
    salary_min_viable REAL,
    location_preference TEXT,
    relocation_conditions TEXT,
    work_mode_preference TEXT,
    personal_concerns TEXT,
    environment_avoid_keywords TEXT,
    environment_prefer_keywords TEXT,
    min_score_to_recommend INTEGER DEFAULT 45,
    cv_version_id INTEGER REFERENCES cv_versions(id)
);

CREATE TABLE IF NOT EXISTS offer_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    cv_version_id INTEGER REFERENCES cv_versions(id),
    evaluated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    skills_hard_match INTEGER,
    experience_match INTEGER,
    education_match INTEGER,
    location_match INTEGER,
    trajectory_coherence INTEGER,
    recency_relevance INTEGER,
    market_competitiveness INTEGER,
    penalty INTEGER DEFAULT 0,
    penalty_breakdown TEXT,
    match_score INTEGER,
    recommendation TEXT,
    company_fit_score INTEGER,
    environment_compatibility TEXT,
    company_red_flags TEXT,
    company_green_flags TEXT,
    hr_concerns TEXT,
    strengths TEXT,
    red_flags TEXT,
    gemma_verdict TEXT,
    apply_recommendation TEXT,
    model_technical TEXT DEFAULT 'qwen2.5-coder:7b',
    model_hr TEXT DEFAULT 'gemma4:e4b',
    processing_ms INTEGER,
    sent_via_telegram INTEGER DEFAULT 0,
    sent_at DATETIME
);
CREATE INDEX IF NOT EXISTS idx_evaluations_offer_id ON offer_evaluations(offer_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_match_score ON offer_evaluations(match_score);
CREATE INDEX IF NOT EXISTS idx_evaluations_evaluated_at ON offer_evaluations(evaluated_at);

CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at DATETIME NOT NULL DEFAULT (datetime('now')),
    query_params TEXT,
    offers_fetched INTEGER DEFAULT 0,
    new_offers INTEGER DEFAULT 0,
    evaluated INTEGER DEFAULT 0,
    errors TEXT,
    duration_ms INTEGER,
    status TEXT DEFAULT 'ok'
);

CREATE TABLE IF NOT EXISTS market_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL UNIQUE,
    calculated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    total_offers_compatible INTEGER,
    new_offers_this_week INTEGER,
    avg_offers_per_day REAL,
    avg_inscriptions_junior INTEGER,
    inscriptions_trend TEXT,
    top_skills_week TEXT,
    emerging_skills TEXT,
    avg_salary_junior REAL,
    salary_trend TEXT,
    pct_remote REAL,
    pct_hybrid REAL,
    pct_onsite REAL,
    market_temperature TEXT,
    weekly_summary TEXT
);

CREATE TABLE IF NOT EXISTS strategic_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    trigger_type TEXT NOT NULL,
    insight_text TEXT NOT NULL,
    data_snapshot TEXT,
    action_suggested TEXT,
    sent_telegram INTEGER DEFAULT 0,
    user_acted INTEGER DEFAULT 0,
    outcome_notes TEXT
);
EOF

echo "=== PASO 7: init_db.py ==="
cat > src/db/init_db.py << 'EOF'
"""
Inicializa la base de datos SQLite desde schema.sql.
Uso: python src/db/init_db.py
"""
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "src" / "db" / "schema.sql"
DB_PATH = PROJECT_ROOT / os.getenv("DB_PATH", "data/jobs.db")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema no encontrado: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema_sql)
        conn.commit()

    log.info("Base de datos inicializada en: %s", DB_PATH)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
    log.info("Tablas creadas (%d): %s", len(tables), ", ".join(tables))


if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        log.error("Error inicializando DB: %s", e)
        raise SystemExit(1) from e
EOF

echo "=== PASO 8: ollama_client.py ==="
cat > src/utils/ollama_client.py << 'EOF'
"""
Wrapper para llamadas a Ollama con reintentos, backoff y validacion JSON.
Modelos secuenciales — nunca en paralelo (VRAM limitada).
"""
import json
import logging
import time
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_TIMEOUT = 180

MODEL_TECHNICAL = "qwen2.5-coder:7b"
MODEL_HR = "gemma4:e4b"

MODEL_TEMPERATURES: dict[str, float] = {
    MODEL_TECHNICAL: 0.1,
    MODEL_HR: 0.4,
}


class OllamaError(Exception):
    """Error en llamada a Ollama."""


class OllamaJSONError(OllamaError):
    """El modelo no devolvio JSON valido tras reintentos."""


def _call_ollama_raw(model: str, prompt: str, temperature: float | None = None) -> str:
    """Llamada directa a la API de Ollama. Sin reintentos."""
    temp = temperature if temperature is not None else MODEL_TEMPERATURES.get(model, 0.1)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temp, "num_ctx": 4096},
    }
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(f"Ollama no disponible en {OLLAMA_BASE_URL}: {e}") from e
    except requests.exceptions.Timeout:
        raise OllamaError(f"Timeout ({OLLAMA_TIMEOUT}s) con modelo {model}")
    except requests.exceptions.HTTPError as e:
        raise OllamaError(f"HTTP {e.response.status_code} desde Ollama: {e}") from e


def _extract_json(text: str) -> Any:
    """Extrae JSON de respuesta del modelo, manejando texto extra."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if "```" in text:
        for block in text.split("```"):
            cleaned = block.strip().lstrip("json").strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue
    for sc, ec in [("{", "}"), ("[", "]")]:
        s, e = text.find(sc), text.rfind(ec)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                continue
    raise OllamaJSONError(f"No se pudo extraer JSON de: {text[:200]}...")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(OllamaError),
    reraise=True,
)
def ollama_call(
    model: str,
    prompt: str,
    expect_json: bool = False,
    temperature: float | None = None,
    json_retry_instruction: str = "\n\nResponde UNICAMENTE con JSON valido, sin texto adicional.",
) -> str | Any:
    """
    Llama a Ollama con reintentos y validacion JSON opcional.
    Returns: str si expect_json=False, dict/list si expect_json=True.
    Raises: OllamaError, OllamaJSONError
    """
    log.debug("Llamando a %s (expect_json=%s)", model, expect_json)
    start = time.time()
    text = _call_ollama_raw(model, prompt, temperature)

    if not expect_json:
        log.debug("Respuesta de %s en %dms", model, int((time.time() - start) * 1000))
        return text

    try:
        result = _extract_json(text)
        log.debug("JSON valido de %s en %dms", model, int((time.time() - start) * 1000))
        return result
    except OllamaJSONError:
        log.warning("Respuesta no-JSON de %s, reintentando...", model)

    text_retry = _call_ollama_raw(model, prompt + json_retry_instruction, temperature)
    try:
        result = _extract_json(text_retry)
        log.debug("JSON valido de %s en segundo intento", model)
        return result
    except OllamaJSONError as e:
        log.error("No se obtuvo JSON valido de %s tras 2 intentos", model)
        raise OllamaJSONError(f"Modelo {model} no devolvio JSON valido") from e


def check_ollama_connection() -> dict[str, bool]:
    """Verifica disponibilidad de Ollama y modelos necesarios."""
    status: dict[str, bool] = {MODEL_TECHNICAL: False, MODEL_HR: False}
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        available = {m["name"] for m in r.json().get("models", [])}
        for model in status:
            status[model] = any(
                m == model or m.startswith(model.split(":")[0]) for m in available
            )
            log.info("[%s] %s", "OK" if status[model] else "FALTA", model)
    except requests.exceptions.ConnectionError:
        log.error("Ollama no esta ejecutandose en %s", OLLAMA_BASE_URL)
    return status


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    status = check_ollama_connection()
    if all(status.values()):
        result = ollama_call(
            model=MODEL_TECHNICAL,
            prompt='Responde con este JSON exacto: {"status": "ok", "test": true}',
            expect_json=True,
        )
        log.info("Test exitoso: %s", result)
    else:
        log.error("Modelos no disponibles. Ejecuta: ollama list")
EOF

echo "=== PASO 9: tests/test_phase1.py ==="
cat > tests/test_phase1.py << 'EOF'
"""
Test Fase 1 — verifica cimientos del sistema.
Uso: python tests/test_phase1.py
"""
import logging
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)
PASS, FAIL, WARN = "OK", "FAIL", "WARN"


def test_env_vars() -> bool:
    log.info("-- TEST 1: Variables de entorno --")
    required = ["INFOJOBS_CLIENT_ID", "INFOJOBS_CLIENT_SECRET", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    ok = True
    for var in required:
        if os.getenv(var):
            log.info("[%s] %s configurada", PASS, var)
        else:
            log.warning("[%s] %s NO configurada", FAIL, var)
            ok = False
    return ok


def test_database() -> bool:
    log.info("-- TEST 2: Base de datos --")
    db_path = PROJECT_ROOT / os.getenv("DB_PATH", "data/jobs.db")

    if not db_path.exists():
        log.warning("[%s] DB no existe, inicializando...", WARN)
        from src.db.init_db import init_db
        init_db()

    expected = {
        "offers", "companies", "candidate_profile", "cv_versions",
        "offer_evaluations", "search_runs", "market_signals", "strategic_insights"
    }
    with sqlite3.connect(db_path) as conn:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    missing = expected - existing
    if missing:
        log.error("[%s] Tablas faltantes: %s", FAIL, missing)
        return False

    log.info("[%s] Tablas OK: %s", PASS, ", ".join(sorted(existing)))
    return True


def test_ollama() -> bool:
    log.info("-- TEST 3: Ollama --")
    try:
        from src.utils.ollama_client import MODEL_HR, MODEL_TECHNICAL, check_ollama_connection, ollama_call

        status = check_ollama_connection()

        if not status[MODEL_TECHNICAL]:
            log.error("[%s] qwen2.5-coder:7b no disponible", FAIL)
            return False
        if not status[MODEL_HR]:
            log.warning("[%s] gemma4:e4b no disponible — verifica con: ollama list", WARN)

        result = ollama_call(
            model=MODEL_TECHNICAL,
            prompt='Devuelve exactamente este JSON: {"status": "ok", "numero": 42}',
            expect_json=True,
        )
        assert isinstance(result, dict) and result.get("status") == "ok", f"JSON incorrecto: {result}"
        log.info("[%s] qwen2.5 JSON OK: %s", PASS, result)
        return True
    except Exception as e:
        log.error("[%s] Ollama: %s", FAIL, e)
        return False


def test_infojobs() -> bool:
    log.info("-- TEST 4: InfoJobs API --")
    import requests
    from requests.auth import HTTPBasicAuth

    cid, csec = os.getenv("INFOJOBS_CLIENT_ID"), os.getenv("INFOJOBS_CLIENT_SECRET")
    if not cid or not csec:
        log.warning("[%s] Credenciales InfoJobs no configuradas — saltando", WARN)
        return True
    try:
        r = requests.get(
            "https://api.infojobs.net/api/7/offer",
            params={"q": "data analyst", "maxResults": 1},
            auth=HTTPBasicAuth(cid, csec),
            timeout=15,
        )
        if r.status_code == 200:
            log.info("[%s] InfoJobs OK — %d ofertas", PASS, r.json().get("totalResults", 0))
            return True
        elif r.status_code == 401:
            log.error("[%s] Credenciales invalidas (401)", FAIL)
            return False
        else:
            log.warning("[%s] InfoJobs respondio %d", WARN, r.status_code)
            return False
    except Exception as e:
        log.error("[%s] InfoJobs: %s", FAIL, e)
        return False


def test_telegram() -> bool:
    log.info("-- TEST 5: Telegram --")
    import requests

    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("[%s] Credenciales Telegram no configuradas — saltando", WARN)
        return True
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "Job Intelligence Agent — test Fase 1 OK"},
            timeout=10,
        )
        if r.status_code == 200:
            log.info("[%s] Telegram OK", PASS)
            return True
        else:
            log.error("[%s] Telegram %d: %s", FAIL, r.status_code, r.text)
            return False
    except Exception as e:
        log.error("[%s] Telegram: %s", FAIL, e)
        return False


def main() -> None:
    log.info("=" * 45)
    log.info("  TEST FASE 1 — Job Intelligence Agent")
    log.info("=" * 45)

    results = {
        "env_vars": test_env_vars(),
        "database": test_database(),
        "ollama":   test_ollama(),
        "infojobs": test_infojobs(),
        "telegram": test_telegram(),
    }

    log.info("=" * 45)
    all_ok = True
    for name, ok in results.items():
        log.info("  [%s] %s", PASS if ok else FAIL, name)
        if not ok:
            all_ok = False

    if all_ok:
        log.info("Fase 1 completada. Continuar con Fase 2.")
    else:
        log.warning("Tests fallidos. Revisar antes de continuar.")
    log.info("=" * 45)


if __name__ == "__main__":
    main()
EOF

echo ""
echo "=== VERIFICACION DE SINTAXIS PYTHON ==="
python3 -c "import ast; ast.parse(open('src/utils/ollama_client.py').read()); print('[OK] ollama_client.py')"
python3 -c "import ast; ast.parse(open('src/db/init_db.py').read()); print('[OK] init_db.py')"
python3 -c "import ast; ast.parse(open('tests/test_phase1.py').read()); print('[OK] test_phase1.py')"

echo ""
echo "=== ESTRUCTURA FINAL ==="
find . -not -path './.venv/*' -not -path './.git/*' | sort | grep -v __pycache__ | grep -v ".pyc"

echo ""
echo "Proximos pasos:"
echo "  1. cp .env.example .env  &&  nano .env"
echo "  2. pip install -r requirements.txt"
echo "  3. python src/db/init_db.py"
echo "  4. python src/utils/ollama_client.py"
echo "  5. python tests/test_phase1.py"
