"""
Pipeline: evaluación de ofertas con qwen2.5 (técnico) + gemma4 (HR).
Procesa ofertas clasificadas (relevance_flag NOT NULL, is_evaluated=0).
"""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402
from src.utils.ollama_client import MODEL_HR, MODEL_TECHNICAL, ollama_call  # noqa: E402

log = logging.getLogger(__name__)


def _clamp(val, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


RATING = {
    (75, 101): "Prioritario",
    (55, 75): "Aplicar",
    (35, 55): "Con expectativas bajas",
    (0, 35): "No aplicar",
}


def get_rating(score: int) -> str:
    for (low, high), label in RATING.items():
        if low <= score < high:
            return label
    return "No aplicar"


def load_perfil() -> str:
    perfil_path = Path(__file__).resolve().parent.parent.parent / "PERFIL.md"
    return perfil_path.read_text(encoding="utf-8")


def get_pending_offers(limit: int = 10) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT id, title, company_name, city, work_mode,
               description_clean, skills_required,
               relevance_flag, role_normalized,
               salary_min, salary_max, published_at
        FROM offers
        WHERE relevance_flag IS NOT NULL
          AND is_evaluated = 0
        ORDER BY published_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def evaluate_technical(offer: dict, perfil: str) -> dict:
    """qwen2.5 evalúa bloque técnico (60 pts). Sin think, output JSON directo."""
    skills = offer.get("skills_required") or "[]"
    prompt = f"""Evalúa el match técnico entre este perfil y esta oferta.
Sé PESIMISTA y HONESTO. Penaliza ausencias aunque sean parciales.

PERFIL:
{perfil[:3000]}

OFERTA:
Título: {offer["title"]}
Empresa: {offer["company_name"]}
Skills requeridas: {skills}
Descripción: {(offer.get("description_clean") or "")[:1500]}

Devuelve SOLO este JSON sin texto adicional:
{{
  "skills_hard_match": <int 0-25>,
  "experience_match": <int 0-15>,
  "education_match": <int 0-10>,
  "location_match": <int 0-10>,
  "reasoning": "<una frase honesta>"
}}"""
    result = ollama_call(
        model=MODEL_TECHNICAL,
        prompt=prompt,
        expect_json=True,
        temperature=0.1,
    )
    return result if isinstance(result, dict) else {}


def evaluate_hr(offer: dict, perfil: str, technical: dict) -> dict:
    """gemma4 evalúa bloque HR (40 pts). Con think=True para razonamiento."""
    prompt = f"""Eres un recruiter senior con criterio real. Evalúa honestamente.
NO suavices la realidad. Evalúa como si tuvieras que defender tu decisión.

PERFIL DEL CANDIDATO:
{perfil[:3000]}

OFERTA:
Título: {offer["title"]} | Empresa: {offer["company_name"]}
Ubicación: {offer.get("city")} | Modalidad: {offer.get("work_mode")}
Descripción: {(offer.get("description_clean") or "")[:1500]}

EVALUACIÓN TÉCNICA PREVIA:
{json.dumps(technical, ensure_ascii=False)}

EVALÚA:
1. ¿El trayecto profesional tiene sentido para este puesto?
2. ¿El gap laboral es descalificante para esta oferta concreta?
3. ¿La empresa/cultura presentan factores relevantes?
   IMPORTANTE: los factores de entorno NO son filtros, son contexto
   de priorización y preparación para entrevista.
4. ¿Qué haría un recruiter real con este CV en el primer filtro?
5. Dado el contexto personal, ¿vale la pena invertir energía aquí?

Devuelve SOLO este JSON:
{{
  "trajectory_coherence": <int 0-15>,
  "recency_relevance": <int 0-15>,
  "market_competitiveness": <int 0-10>,
  "penalty": <int 0-30>,
  "penalty_breakdown": {{"motivo": <puntos>}},
  "environment_compatibility": "<alta|media|baja>",
  "hr_concerns": ["<string>"],
  "strengths": ["<string>"],
  "red_flags": ["<string>"],
  "interview_prep": ["<consejo concreto>"],
  "verdict": "<párrafo libre honesto>"
}}"""
    result = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
        temperature=0.0,
        think=True,
    )
    return result if isinstance(result, dict) else {}


def save_evaluation(
    offer_id: int,
    technical: dict,
    hr: dict,
    match_score: int,
    recommendation: str,
    processing_ms: int,
) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO offer_evaluations (
            offer_id, skills_hard_match, experience_match,
            education_match, location_match,
            trajectory_coherence, recency_relevance,
            market_competitiveness, penalty, penalty_breakdown,
            match_score, recommendation,
            environment_compatibility, hr_concerns,
            strengths, red_flags, gemma_verdict,
            apply_recommendation, processing_ms,
            model_technical, model_hr
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            offer_id,
            technical.get("skills_hard_match", 0),
            technical.get("experience_match", 0),
            technical.get("education_match", 0),
            technical.get("location_match", 0),
            hr.get("trajectory_coherence", 0),
            hr.get("recency_relevance", 0),
            hr.get("market_competitiveness", 0),
            hr.get("penalty", 0),
            json.dumps(hr.get("penalty_breakdown", {}), ensure_ascii=False),
            match_score,
            recommendation,
            hr.get("environment_compatibility"),
            json.dumps(hr.get("hr_concerns", []), ensure_ascii=False),
            json.dumps(hr.get("strengths", []), ensure_ascii=False),
            json.dumps(hr.get("red_flags", []), ensure_ascii=False),
            hr.get("verdict"),
            recommendation,
            processing_ms,
            MODEL_TECHNICAL,
            MODEL_HR,
        ),
    )
    cur.execute("UPDATE offers SET is_evaluated=1 WHERE id=?", (offer_id,))
    conn.commit()
    conn.close()


def run_evaluate(limit: int = 10) -> dict:
    perfil = load_perfil()
    offers = get_pending_offers(limit)
    log.info("Ofertas pendientes de evaluar: %d", len(offers))

    stats = {"evaluated": 0, "errors": 0, "scores": []}

    for offer in offers:
        t0 = time.monotonic()
        try:
            log.info("Evaluando: %s", offer["title"])

            technical = evaluate_technical(offer, perfil)
            if not technical:
                log.warning("qwen2.5 no devolvió resultado para: %s", offer["title"])
                stats["errors"] += 1
                continue

            hr = evaluate_hr(offer, perfil, technical)
            if not hr:
                log.warning("gemma4 no devolvió resultado para: %s", offer["title"])
                stats["errors"] += 1
                continue

            bloque_a = (
                _clamp(technical.get("skills_hard_match", 0), 0, 25)
                + _clamp(technical.get("experience_match", 0), 0, 15)
                + _clamp(technical.get("education_match", 0), 0, 10)
                + _clamp(technical.get("location_match", 0), 0, 10)
            )
            bloque_b = (
                _clamp(hr.get("trajectory_coherence", 0), 0, 15)
                + _clamp(hr.get("recency_relevance", 0), 0, 15)
                + _clamp(hr.get("market_competitiveness", 0), 0, 10)
            )
            penalty = _clamp(hr.get("penalty", 0), 0, 30)
            match_score = max(0, min(100, bloque_a + bloque_b - penalty))
            recommendation = get_rating(match_score)

            ms = int((time.monotonic() - t0) * 1000)
            save_evaluation(offer["id"], technical, hr, match_score, recommendation, ms)

            log.info("✓ %s → %d/100 (%s)", offer["title"], match_score, recommendation)
            stats["evaluated"] += 1
            stats["scores"].append(match_score)

        except Exception as e:
            log.error("Error evaluando %s: %s", offer["title"], e)
            stats["errors"] += 1

    if stats["scores"]:
        stats["avg_score"] = sum(stats["scores"]) // len(stats["scores"])

    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    stats = run_evaluate(limit=3)
    log.info("Completado: %s", stats)
