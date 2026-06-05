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
import logging
import logging.handlers
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HASH_PATH = PROJECT_ROOT / ".cv_hash"
CV_PATH = PROJECT_ROOT / "assets/cv.pdf"
PERFIL_PATH = PROJECT_ROOT / "PERFIL.md"


def setup_logging() -> None:
    """Configura logging con rotación de archivos."""
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "pipeline.log"

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)


def run_pipeline(
    skip_fetch: bool = False,
    dry_run: bool = False,
    limit: int = 30,
    skip_cv_check: bool = False,
) -> None:
    setup_logging()

    # Configurar consola inmediatamente para que warnings se vean
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(console_format)
    logging.getLogger().addHandler(console)

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
            log.warning(
                "[CV] CV actualizado. Ejecuta: "
                "PYTHONPATH=. python src/onboarding/run.py"
            )
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

    log.info("═══════════════════════════════════")
    log.info("  Job Intelligence Agent — Pipeline")
    log.info("═══════════════════════════════════")

    # PASO 1: Fetch
    if skip_fetch:
        log.info("[1/4] Fetch — saltado (--skip-fetch)")
    else:
        log.info("[1/4] Fetch — descargando ofertas de InfoJobs...")
        from src.pipeline.fetch import run_fetch

        new_offers = run_fetch()
        log.info("[1/4] Fetch — %d ofertas nuevas", new_offers)

    # PASO 2: Classify
    log.info("[2/4] Classify — clasificando roles...")
    from src.pipeline.role_classifier import run_classifier

    classified = run_classifier()
    log.info("[2/4] Classify — %d ofertas clasificadas", classified)

    # PAS0 2.5: Enrich companies (optional - degrada gracefully)
    log.info("[2.5/4] Enrich — poblando datos de empresas...")
    from src.pipeline.fetch_company import run as run_fetch_company

    try:
        enrich_result = run_fetch_company(limit=limit)
        log.info(
            "[2.5/4] Enrich — %d nuevas, %d actualizadas, %d enlazadas",
            enrich_result["new"],
            enrich_result["updated"],
            enrich_result["linked"],
        )
    except Exception as e:
        log.warning("[2.5/4] Enrich — falló (DB necesita migración): %s", e)

    # PASO 3: Evaluate
    log.info("[3/4] Evaluate — puntuando con gemma4:e4b...")
    from src.pipeline.evaluate import run_evaluate

    stats = run_evaluate(limit=limit)
    log.info("[3/4] Evaluate — %s", stats)

    # PASO 4: Send
    if dry_run:
        log.info("[4/4] Send — saltado (--dry-run)")
    else:
        log.info("[4/4] Send — enviando a Telegram...")
        from src.telegram.send import send_daily

        send_daily()
        log.info("[4/4] Send — OK")

    log.info("Pipeline completado")


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
    parser.add_argument(
        "--skip-fetch", action="store_true", help="Saltar fetch de Apify"
    )
    parser.add_argument("--dry-run", action="store_true", help="No enviar a Telegram")
    parser.add_argument(
        "--skip-cv-check", action="store_true", help="Saltar verificación de CV"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Máximo de ofertas a procesar (default: 30)",
    )
    args = parser.parse_args()
    run_pipeline(
        skip_fetch=args.skip_fetch,
        dry_run=args.dry_run,
        limit=args.limit,
        skip_cv_check=args.skip_cv_check,
    )
