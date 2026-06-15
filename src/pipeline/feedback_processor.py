"""Procesador de feedback acumulado.

Script que procesa el feedback en user_feedback (processed=0)
y genera/actualiza un resumen en user_psychology.

Uso:
    python -m src.pipeline.feedback_processor
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

from src.db.init_db import get_connection  # noqa: E402
from src.utils.ollama_client import MODEL_TECHNICAL, ollama_call  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

MIN_FEEDBACK_THRESHOLD = 3


def get_pending_feedback() -> list[dict]:
    """Obtiene todos los feedbacks pendientes de procesar."""
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT id, offer_id, feedback_type, raw_text, created_at
        FROM user_feedback
        WHERE processed = 0
        ORDER BY created_at ASC
        """,
    ).fetchall()
    conn.close()
    columns = ["id", "offer_id", "feedback_type", "raw_text", "created_at"]
    return [dict(zip(columns, row)) for row in rows]


def mark_feedback_processed(feedback_ids: list[int]) -> None:
    """Marca los feedbacks como procesados."""
    if not feedback_ids:
        return
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" * len(feedback_ids))
    cur.execute(
        f"UPDATE user_feedback SET processed = 1 WHERE id IN ({placeholders})",
        feedback_ids,
    )
    conn.commit()
    conn.close()


def get_latest_psychology() -> dict | None:
    """Obtiene el último registro de user_psychology."""
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT id, raw_feedback, summary, key_insights, version
        FROM user_psychology
        ORDER BY id DESC
        LIMIT 1
        """,
    ).fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "raw_feedback": row[1],
            "summary": row[2],
            "key_insights": row[3],
            "version": row[4],
        }
    return None


def save_psychology(summary: str, key_insights: str, raw_feedback: str) -> None:
    """Guarda o actualiza el resumen en user_psychology."""
    conn = get_connection()
    cur = conn.cursor()

    existing = cur.execute("SELECT id FROM user_psychology ORDER BY id DESC LIMIT 1").fetchone()

    if existing:
        cur.execute(
            """
            UPDATE user_psychology
            SET raw_feedback = ?, summary = ?, key_insights = ?,
                last_updated = datetime('now'), version = version + 1
            WHERE id = ?
            """,
            (raw_feedback, summary, key_insights, existing[0]),
        )
    else:
        cur.execute(
            """
            INSERT INTO user_psychology (raw_feedback, summary, key_insights, version)
            VALUES (?, ?, ?, 1)
            """,
            (raw_feedback, summary, key_insights),
        )
    conn.commit()
    conn.close()


def build_prompt(feedbacks: list[dict], previous_summary: str | None) -> str:
    """Construye el prompt para gemma4."""
    grouped = {"f1": [], "f2": [], "f3": [], "dia": []}

    for fb in feedbacks:
        fb_type = fb["feedback_type"]
        if fb_type in grouped:
            grouped[fb_type].append(fb["raw_text"])

    context = f"Resumen previo del usuario:\n{previous_summary}\n\n" if previous_summary else ""

    prompt = f"""Eres un asistente que analiza feedback de un candidato sobre ofertas de trabajo.

{context}## Feedback reciente

### Ofertas que le gustaron (/f1):
{chr(10).join(f"- {t}" for t in grouped["f1"]) if grouped["f1"] else "Ninguno"}

### Ofertas que le disgustaron (/f2):
{chr(10).join(f"- {t}" for t in grouped["f2"]) if grouped["f2"] else "Ninguno"}

### Ofertas con comentarios mixtos (/f3):
{chr(10).join(f"- {t}" for t in grouped["f3"]) if grouped["f3"] else "Ninguno"}

### Estado emocional (/dia):
{chr(10).join(f"- {t}" for t in grouped["dia"]) if grouped["dia"] else "Ninguno"}

---

Genera un resumen estructurado en JSON con este formato:
{{
  "patrones_preferencia": "<qué tipos de ofertas le interesan>",
  "estado_emocional": "<estado emocional recurrente>",
  "red_flags_personales": ["<factores que le hacen rechazar ofertas>"],
  "oportunidades_valoradas": ["<aspectos que valora en las ofertas>"],
  "notas_adicionales": "<observaciones relevantes>"
}}

Responde SOLO JSON válido.
"""
    return prompt


def run() -> dict:
    """Función principal del procesador de feedback."""
    log.info("[Feedback] Iniciando procesamiento de feedback...")

    feedbacks = get_pending_feedback()

    if len(feedbacks) < MIN_FEEDBACK_THRESHOLD:
        log.info(
            "[Feedback] Solo %d feedbacks pendientes (mínimo %d). No se procesa.",
            len(feedbacks),
            MIN_FEEDBACK_THRESHOLD,
        )
        return {
            "processed": 0,
            "skipped": len(feedbacks),
            "reason": "below_threshold",
        }

    log.info("[Feedback] Procesando %d feedbacks...", len(feedbacks))

    previous = get_latest_psychology()
    previous_summary = previous.get("summary") if previous else None

    prompt = build_prompt(feedbacks, previous_summary)

    result = ollama_call(
        model=MODEL_TECHNICAL,
        prompt=prompt,
        expect_json=True,
        temperature=0.3,
    )

    if not result or not isinstance(result, dict):
        log.error("[Feedback] Error al llamar al modelo")
        return {"processed": 0, "error": "model_call_failed"}

    summary = result.get("patrones_preferencia", "")
    key_insights = json.dumps(result, ensure_ascii=False)

    raw_text = "\n".join(f"[{fb['feedback_type']}] {fb['raw_text']}" for fb in feedbacks)

    save_psychology(summary, key_insights, raw_text)

    feedback_ids = [fb["id"] for fb in feedbacks]
    mark_feedback_processed(feedback_ids)

    log.info("[Feedback] Completado. Nueva versión guardada.")

    return {
        "processed": len(feedbacks),
        "version": (previous.get("version") if previous else 0) + 1,
    }


if __name__ == "__main__":
    result = run()
    print(f"Resultado: {result}")
