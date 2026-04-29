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
