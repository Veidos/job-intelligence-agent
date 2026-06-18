"""Bot de Telegram para feedback.

Uso:
    python -m src.telegram.bot
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.telegram.handlers import get_latest_daily_offers, save_feedback
from telegram import Update

load_dotenv()


def setup_logging() -> None:
    """Configura logging con rotación de archivos."""
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "bot.log"

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


log = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("TELEGRAM_USER_ID", "0"))


def require_auth(handler):
    """Decorador: solo permite paso si el user_id coincide con TELEGRAM_USER_ID."""
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if ALLOWED_USER_ID and update.effective_user.id != ALLOWED_USER_ID:
            await update.message.reply_text("No autorizado.")
            return
        return await handler(update, context)
    return wrapper


@require_auth
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /start."""
    await update.message.reply_text(
        "¡Hola! Soy tu asistente de ofertas de trabajo.\n\n"
        "Comandos disponibles:\n"
        "/f1 <feedback> - Feedback sobre oferta 1\n"
        "/f2 <feedback> - Feedback sobre oferta 2\n"
        "/f3 <feedback> - Feedback sobre oferta 3\n"
        "/dia <estado> - Estado emocional del día"
    )


async def feedback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, fb_type: str
) -> None:
    """Handler genérico para /f1, /f2, /f3."""
    text = update.message.text
    parts = text.split(" ", 1)
    feedback_text = parts[1].strip() if len(parts) > 1 else ""

    if not feedback_text:
        await update.message.reply_text(
            f"Usa /{fb_type} <tu feedback>\n\nEjemplo: /{fb_type} Me gusta esta oferta"
        )
        return

    position = {"f1": 0, "f2": 1, "f3": 2}.get(fb_type, 0)
    offer_ids = get_latest_daily_offers()

    if not offer_ids:
        await update.message.reply_text(
            "No hay ofertas del día recientes. Ejecuta el pipeline primero."
        )
        return

    if position >= len(offer_ids):
        await update.message.reply_text(
            f"No existe oferta en posición {position + 1}. "
            f"El último daily tenía {len(offer_ids)} ofertas."
        )
        return

    offer_id = offer_ids[position]
    user_id = update.message.from_user.id

    success = save_feedback(fb_type, feedback_text, offer_id, user_id)

    if success:
        await update.message.reply_text(
            f"Feedback registrado para oferta {position + 1} ✓\n\nGracias por tu opinión."
        )
    else:
        await update.message.reply_text("Error al guardar. Intenta de nuevo.")


@require_auth
async def f1_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await feedback_handler(update, context, "f1")


@require_auth
async def f2_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await feedback_handler(update, context, "f2")


@require_auth
async def f3_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await feedback_handler(update, context, "f3")


@require_auth
async def dia_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /dia."""
    text = update.message.text
    parts = text.split(" ", 1)
    feedback_text = parts[1].strip() if len(parts) > 1 else ""

    if not feedback_text:
        await update.message.reply_text(
            "Usa /dia <tu estado>\n\nEjemplo: /dia Hoy me siento motivado pero cansado"
        )
        return

    user_id = update.message.from_user.id
    success = save_feedback("dia", feedback_text, None, user_id)

    if success:
        await update.message.reply_text("Estado del día registrado ✓\n\nGracias por compartir.")
    else:
        await update.message.reply_text("Error al guardar. Intenta de nuevo.")


@require_auth
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensajes que no son comandos."""
    await update.message.reply_text("Usa /start para ver los comandos disponibles.")


def run_polling() -> None:
    """Ejecuta el bot en modo polling."""
    setup_logging()

    if not TELEGRAM_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN no configurado")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("f1", f1_handler))
    app.add_handler(CommandHandler("f2", f2_handler))
    app.add_handler(CommandHandler("f3", f3_handler))
    app.add_handler(CommandHandler("dia", dia_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    log.info("Iniciando bot en modo polling...")
    app.run_polling()


if __name__ == "__main__":
    run_polling()
