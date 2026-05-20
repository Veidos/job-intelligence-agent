"""
Orquestador del pipeline completo.
Orden: fetch → classify → evaluate → send

Uso:
    PYTHONPATH=. python src/pipeline/run.py
    PYTHONPATH=. python src/pipeline/run.py --skip-fetch
    PYTHONPATH=. python src/pipeline/run.py --dry-run
"""

import argparse
import logging
import logging.handlers
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


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


def run_pipeline(skip_fetch: bool = False, dry_run: bool = False) -> None:
    setup_logging()

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(console_format)
    logging.getLogger().addHandler(console)

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

    # PAS0 2.5: Enrich companies
    log.info("[2.5/4] Enrich — poblando datos de empresas...")
    from src.pipeline.fetch_company import run as run_fetch_company

    enrich_result = run_fetch_company(limit=50)
    log.info(
        "[2.5/4] Enrich — %d nuevas, %d actualizadas, %d enlazadas",
        enrich_result["new"],
        enrich_result["updated"],
        enrich_result["linked"],
    )

    # PASO 3: Evaluate
    log.info("[3/4] Evaluate — puntuando con gemma4:e4b...")
    from src.pipeline.evaluate import run_evaluate

    stats = run_evaluate(limit=20)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-fetch", action="store_true", help="Saltar fetch de Apify"
    )
    parser.add_argument("--dry-run", action="store_true", help="No enviar a Telegram")
    args = parser.parse_args()
    run_pipeline(skip_fetch=args.skip_fetch, dry_run=args.dry_run)
