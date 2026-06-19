"""
Orquestador del pipeline completo.
Orden: fetch → classify → evaluate → send

Uso:
    PYTHONPATH=. python src/pipeline/run.py
    PYTHONPATH=. python src/pipeline/run.py --skip-fetch
    PYTHONPATH=. python src/pipeline/run.py --dry-run
"""

import argparse
import hashlib
import json
import logging
import logging.handlers
import signal
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HASH_PATH = PROJECT_ROOT / ".cv_hash"
CV_PATH = PROJECT_ROOT / "assets/cv.pdf"
PERFIL_PATH = PROJECT_ROOT / "PERFIL.md"


def setup_logging() -> None:
    """Configura logging con rotación de archivos y salida a consola."""
    root = logging.getLogger()
    if root.handlers:
        return
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "pipeline.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def run_pipeline(
    skip_fetch: bool = False,
    dry_run: bool = False,
    limit_eval: int = 30,
    limit_enrich: int = 50,
    skip_cv_check: bool = False,
    since_date: str = "_24_HOURS",
    run_id: int | None = None,
) -> None:
    setup_logging()
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))

    log.info("[Migrate] Verificando schema...")
    from src.db.migrate import run_migration

    run_migration()

    # ── CV freshness check ────────────────────────────────────────
    has_cv = CV_PATH.exists()
    has_perfil = PERFIL_PATH.exists()

    if skip_cv_check:
        log.info("[CV] Check saltado (--skip-cv-check)")

    elif dry_run:
        log.info("[CV] Saltado (--dry-run), se usa PERFIL.md actual")

    elif has_cv and _compute_file_hash(CV_PATH) != _read_hash(HASH_PATH):
        _write_hash(HASH_PATH, _compute_file_hash(CV_PATH))

        if sys.stdin.isatty():
            log.warning("[CV] CV nuevo detectado en assets/cv.pdf")
            reply = input("¿Regenerar PERFIL.md con entrevista? (s/N): ")
            if reply.strip().lower() in ("s", "si", "y", "yes"):
                log.info("[CV] Regenerando PERFIL.md...")
                from src.onboarding.cv_extractor import extract_cv_data
                from src.onboarding.interviewer import run_interview
                from src.onboarding.run import generate_perfil_md

                cv_data = extract_cv_data(CV_PATH)
                interview_data = run_interview(cv_data)
                profile = {**cv_data, **interview_data}
                PERFIL_PATH.write_text(generate_perfil_md(profile), encoding="utf-8")
                log.info("[CV] PERFIL.md regenerado → continuando pipeline")
            else:
                log.warning("[CV] PERFIL.md no actualizado → pipeline detenido")
                return
        else:
            log.warning("[CV] CV actualizado. Ejecuta: PYTHONPATH=. python src/onboarding/run.py")
            log.warning("[CV] Pipeline abortado — CV nuevo sin PERFIL.md actualizado")
            return

    elif not has_perfil and has_cv:
        log.error(
            "[CV] PERFIL.md no encontrado. Ejecuta primero: "
            "PYTHONPATH=. python src/onboarding/run.py --cv assets/cv.pdf"
        )
        return

    elif not has_cv:
        log.warning("[CV] No se encontró assets/cv.pdf — continuando sin verificación")

    else:
        log.info("[CV] PERFIL.md actualizado — continuando")
    # ── fin CV check ──────────────────────────────────────────────

    t0 = time.monotonic()

    log.info("═══════════════════════════════════")
    log.info("  Job Intelligence Agent — Pipeline")
    log.info("═══════════════════════════════════")

    errors: list[str] = []
    new_offers = 0
    offers_fetched = 0
    evaluated = 0

    try:
        # PASO 1: Fetch
        if skip_fetch:
            log.info("[1/4] Fetch — saltado (--skip-fetch)")
        else:
            log.info("[1/4] Fetch — descargando ofertas de InfoJobs...")
            from src.pipeline.fetch import run_fetch_scraper

            fetch_result = run_fetch_scraper(since_date=since_date, dry_run=dry_run)
            new_offers = fetch_result["new"]
            offers_fetched = fetch_result["total"]
            log.info("[1/4] Fetch — %d nuevas de %d scrapeadas", new_offers, offers_fetched)

        # PASO 2: Classify
        log.info("[2/4] Classify — clasificando roles...")
        from src.pipeline.role_classifier import run_classifier

        classified = run_classifier()
        log.info("[2/4] Classify — %d ofertas clasificadas", classified)

        # PAS0 2.5: Enrich companies (optional - degrada gracefully)
        log.info("[2.5/4] Enrich — poblando datos de empresas...")
        from src.pipeline.fetch_company import run as run_fetch_company

        try:
            enrich_result = run_fetch_company(limit=limit_enrich)
            log.info(
                "[2.5/4] Enrich — %d nuevas, %d actualizadas, %d errores, %d pendientes",
                enrich_result["enriched"],
                enrich_result["linked"],
                enrich_result["errors"],
                enrich_result["pending"],
            )
        except Exception as e:
            log.warning("[2.5/4] Enrich — falló (DB necesita migración): %s", e)
            errors.append(f"enrich: {e}")

        # PASO 3: Evaluate
        log.info("[3/4] Evaluate — puntuando con gemma4:e4b...")
        from src.pipeline.evaluate import run_evaluate

        stats = run_evaluate(limit=limit_eval)
        evaluated = stats.get("evaluated", 0)
        log.info("[3/4] Evaluate — %s", stats)

        # PASO 4: Send
        if dry_run:
            log.info("[4/4] Send — saltado (--dry-run)")
        else:
            try:
                log.info("[4/4] Send — enviando a Telegram...")
                from src.telegram.send import send_daily

                send_daily()
                log.info("[4/4] Send — OK")
            except Exception as e:
                log.error("[4/4] Send — error: %s", e)
                errors.append(f"send: {e}")

        elapsed = int((time.monotonic() - t0) * 1000)
        log.info("Pipeline completado (%d ms)", elapsed)

        from src.utils.ollama_client import get_llm_metrics

        llm_metrics = get_llm_metrics()
        if llm_metrics["calls"] > 0:
            log.info("[LLM Metrics] %s", llm_metrics)
    except (SystemExit, KeyboardInterrupt):
        log.warning("Pipeline interrumpido por señal externa")
        elapsed = int((time.monotonic() - t0) * 1000)
        _persist_run(
            errors=[],
            new_offers=new_offers,
            offers_fetched=offers_fetched,
            evaluated=evaluated,
            skip_fetch=skip_fetch,
            dry_run=dry_run,
            limit_eval=limit_eval,
            limit_enrich=limit_enrich,
            since_date=since_date,
            elapsed=elapsed,
            run_id=run_id,
            status_override="stopped",
        )
        return

    except Exception as e:
        log.error("Pipeline falló con excepción: %s", e, exc_info=True)
        elapsed = int((time.monotonic() - t0) * 1000)
        _persist_run(
            errors=[str(e)],
            new_offers=new_offers,
            offers_fetched=offers_fetched,
            evaluated=evaluated,
            skip_fetch=skip_fetch,
            dry_run=dry_run,
            limit_eval=limit_eval,
            limit_enrich=limit_enrich,
            since_date=since_date,
            elapsed=elapsed,
            run_id=run_id,
        )
        return

    _persist_run(
        errors,
        new_offers,
        offers_fetched,
        evaluated,
        skip_fetch,
        dry_run,
        limit_eval,
        limit_enrich,
        since_date,
        elapsed,
        run_id=run_id,
    )


def _persist_run(
    errors: list[str],
    new_offers: int,
    offers_fetched: int,
    evaluated: int,
    skip_fetch: bool,
    dry_run: bool,
    limit_eval: int,
    limit_enrich: int,
    since_date: str,
    elapsed: int,
    run_id: int | None = None,
    status_override: str | None = None,
) -> None:
    from src.db.init_db import get_connection

    params = json.dumps(
        {
            "skip_fetch": skip_fetch,
            "dry_run": dry_run,
            "since_date": since_date,
            "limit_eval": limit_eval,
            "limit_enrich": limit_enrich,
        }
    )
    offers_fetched_val = 0 if skip_fetch else offers_fetched
    errors_val = "; ".join(errors) if errors else None
    status_val = status_override or ("error" if errors else "ok")

    conn = get_connection()
    if run_id:
        conn.execute(
            """UPDATE search_runs
               SET query_params=?, offers_fetched=?, new_offers=?, evaluated=?,
                   errors=?, duration_ms=?, status=?
               WHERE id=?""",
            (params, offers_fetched_val, new_offers, evaluated,
             errors_val, elapsed, status_val, run_id),
        )
    else:
        conn.execute(
            """INSERT INTO search_runs
               (query_params, offers_fetched, new_offers, evaluated, errors, duration_ms, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (params, offers_fetched_val, new_offers, evaluated,
             errors_val, elapsed, status_val),
        )
    conn.commit()
    conn.close()


def _compute_file_hash(path: Path) -> str:
    """SHA-256 del contenido del archivo."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_hash(path: Path) -> str | None:
    """Lee el hash previo guardado. None si no existe."""
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        return None


def _write_hash(path: Path, hash_value: str) -> None:
    """Persiste el hash para futuras comparaciones."""
    path.write_text(hash_value)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fetch", action="store_true", help="Saltar fetch de InfoJobs")
    parser.add_argument("--dry-run", action="store_true", help="No enviar a Telegram")
    parser.add_argument("--skip-cv-check", action="store_true", help="Saltar verificación de CV")
    parser.add_argument(
        "--limit-eval",
        type=int,
        default=30,
        help="Máximo de ofertas a evaluar (0 = sin límite, default: 30)",
    )
    parser.add_argument(
        "--limit-enrich",
        type=int,
        default=50,
        help="Máximo de empresas a enriquecer (0 = sin límite, default: 50)",
    )
    parser.add_argument(
        "--since-date",
        default="_24_HOURS",
        choices=["_24_HOURS", "_7_DAYS", "_15_DAYS", "ANY"],
        help="Filtro temporal (default: _24_HOURS)",
    )
    parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="ID de search_runs para UPDATE (dashboard interno)",
    )
    args = parser.parse_args()
    run_pipeline(
        skip_fetch=args.skip_fetch,
        dry_run=args.dry_run,
        limit_eval=args.limit_eval,
        limit_enrich=args.limit_enrich,
        skip_cv_check=args.skip_cv_check,
        since_date=args.since_date,
        run_id=args.run_id,
    )
