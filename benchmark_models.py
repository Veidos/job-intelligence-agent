#!/usr/bin/env python3
"""
Benchmark comparativo de modelos para job-intelligence-agent.
Prueba classify + technical + HR sobre 4 ofertas seleccionadas.
Cada modelo actúa como MODEL_TECHNICAL (classify + technical).
gemma4:e4b siempre actúa como MODEL_HR (no cambia).
"""

import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.db.init_db import get_connection
from src.utils.ollama_client import ollama_call

OFFER_IDS = [162, 198, 5, 15]

MODELS_TECHNICAL = [
    "qwen2.5-coder:7b",   # baseline actual
    "llama3.1:8b",
    "qwen2.5:7b",
    "qwen3:8b",
    "deepseek-r1:7b",
    "deepseek-r1:8b",
]

MODEL_HR = "gemma4:e4b"


def load_offers(ids: list[int]) -> list[dict]:
    conn = get_connection()
    result = []
    for oid in ids:
        r = conn.execute("""
            SELECT id, title, company_name, city, work_mode,
                   description_clean, skills_required, relevance_flag
            FROM offers WHERE id = ?
        """, (oid,)).fetchone()
        if r:
            result.append({
                "id": r[0], "title": r[1], "company_name": r[2],
                "city": r[3], "work_mode": r[4],
                "description_clean": r[5], "skills_required": r[6],
                "relevance_flag": r[7],
            })
    conn.close()
    return result


def classify_offer(offer: dict, model: str, perfil: str) -> dict:
    catalog = [
        "data_analyst", "data_scientist", "ml_engineer", "bi_analyst",
        "data_engineer", "operations_analyst", "quality_analyst",
        "process_engineer", "technical_support", "temporal",
    ]
    prompt = f"""Eres un clasificador de ofertas de empleo.
Dado este catálogo de roles: {catalog}
Y este perfil de candidato: {perfil[:1500]}

Analiza esta oferta:
Título: {offer["title"]}
Descripción: {(offer.get("description_clean") or "")[:1500]}

Decide:
1. ¿A qué role del catálogo corresponde realmente esta oferta basándote en los REQUISITOS?
2. Si no encaja en ninguno, propón un nombre nuevo en snake_case.
3. ¿Qué relevance_flag tiene para este candidato?
   core: requisitos coinciden >70% con el perfil
   adjacent: coinciden 40-70%
   stretch: coinciden 20-40%
   temporal: trabajo puente viable
Sé CONSERVADOR. En caso de duda elige el nivel INFERIOR.

Responde SOLO JSON:
{{
  "role_normalized": "nombre_del_catalogo_o_nuevo",
  "relevance_flag": "core|adjacent|stretch|temporal",
  "reasoning": "string breve"
}}"""
    return ollama_call(model=model, prompt=prompt, expect_json=True, temperature=0.1) or {}


def evaluate_technical(offer: dict, model: str, perfil: str) -> dict:
    skills = offer.get("skills_required") or "[]"
    prompt = f"""Evalúa el match técnico entre este perfil y esta oferta.

REGLAS CRÍTICAS (obligatorias):
- Evalúa SOLO lo que la oferta exige explícitamente
- Si la oferta NO pide experiencia previa → experience_match = 18-20
- Si el candidato TIENE las skills pedidas → puntuación alta para esas skills
- NO penalices por skills que el candidato tiene pero la oferta no pide
- location_match: remoto=5, híbrido=3, presencial-otra-ciudad=1, presencial-sin-posibilidad-remoto=0

PERFIL:
{perfil[:3000]}

OFERTA:
Título: {offer["title"]}
Empresa: {offer["company_name"]}
Skills requeridas: {skills}
Descripción: {(offer.get("description_clean") or "")[:1500]}

Devuelve SOLO este JSON sin texto adicional:
{{
  "skills_hard_match": <int 0-30>,
  "experience_match": <int 0-20>,
  "education_match": <int 0-10>,
  "location_match": <int 0-5>,
  "reasoning": "<una frase honesta>"
}}"""
    return ollama_call(model=model, prompt=prompt, expect_json=True, temperature=0.1) or {}


def evaluate_hr(offer: dict, perfil: str, technical: dict) -> dict:
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

IMPORTANTE: El salario mínimo viable del candidato NO es un factor de penalización.
La penalty es SOLO para: gap laboral, incoherencia grave de trayectoria, requisitos obligatorios no cumplidos.

EVALÚA:
1. ¿El trayecto profesional tiene sentido para este puesto?
2. ¿El gap laboral es descalificante para esta oferta concreta?
3. ¿La empresa/cultura presentan factores relevantes?
4. ¿Qué haría un recruiter real con este CV en el primer filtro?

Devuelve SOLO este JSON:
{{
  "trajectory_coherence": <int 0-15>,
  "recency_relevance": <int 0-15>,
  "market_competitiveness": <int 0-5>,
  "penalty": <int 0-25>,
  "penalty_breakdown": {{"motivo": <puntos>}},
  "environment_compatibility": "<alta|media|baja>",
  "apply_signal": "<yes|no|maybe>",
  "verdict": "<párrafo libre honesto>"
}}"""
    return ollama_call(model=MODEL_HR, prompt=prompt, expect_json=True, temperature=0.0, think=True) or {}


def _clamp(val, lo, hi):
    return max(lo, min(hi, int(val or 0)))


def calc_score(technical: dict, hr: dict) -> int:
    bloque_a = (
        _clamp(technical.get("skills_hard_match", 0), 0, 30)
        + _clamp(technical.get("experience_match", 0), 0, 20)
        + _clamp(technical.get("education_match", 0), 0, 10)
        + _clamp(technical.get("location_match", 0), 0, 5)
    )
    bloque_b = (
        _clamp(hr.get("trajectory_coherence", 0), 0, 15)
        + _clamp(hr.get("recency_relevance", 0), 0, 15)
        + _clamp(hr.get("market_competitiveness", 0), 0, 5)
    )
    penalty = _clamp(hr.get("penalty", 0), 0, 25)
    return max(0, min(100, bloque_a + bloque_b - penalty))


def get_rating(score: int) -> str:
    if score >= 75: return "Prioritario"
    if score >= 55: return "Aplicar"
    if score >= 35: return "Con expectativas bajas"
    return "No aplicar"


def run_benchmark():
    perfil = Path("PERFIL.md").read_text(encoding="utf-8")
    offers = load_offers(OFFER_IDS)
    results = {}

    for model in MODELS_TECHNICAL:
        print(f"\n{'='*60}")
        print(f"MODELO: {model}")
        print(f"{'='*60}")
        results[model] = []

        for offer in offers:
            print(f"\n  Oferta: [{offer['id']}] {offer['title'][:50]}")
            t0 = time.monotonic()

            t1 = time.monotonic()
            classification = classify_offer(offer, model, perfil)
            t_classify = time.monotonic() - t1

            t1 = time.monotonic()
            technical = evaluate_technical(offer, model, perfil)
            t_technical = time.monotonic() - t1

            t1 = time.monotonic()
            hr = evaluate_hr(offer, perfil, technical)
            t_hr = time.monotonic() - t1

            score = calc_score(technical, hr)
            rating = get_rating(score)
            total_time = time.monotonic() - t0

            bloque_a = (
                _clamp(technical.get("skills_hard_match", 0), 0, 30)
                + _clamp(technical.get("experience_match", 0), 0, 20)
                + _clamp(technical.get("education_match", 0), 0, 10)
                + _clamp(technical.get("location_match", 0), 0, 5)
            )

            results[model].append({
                "offer_id": offer["id"],
                "offer_title": offer["title"],
                "classification": classification,
                "technical": technical,
                "hr_apply_signal": hr.get("apply_signal", "?"),
                "hr_verdict_short": hr.get("verdict", "")[:120],
                "score": score,
                "rating": rating,
                "t_classify": round(t_classify, 1),
                "t_technical": round(t_technical, 1),
                "t_hr": round(t_hr, 1),
                "t_total": round(total_time, 1),
            })

            print(f"  Classify  → role={classification.get('role_normalized','?')} flag={classification.get('relevance_flag','?')} ({t_classify:.1f}s)")
            print(f"  Technical → skills={technical.get('skills_hard_match','?')}/30 exp={technical.get('experience_match','?')}/20 edu={technical.get('education_match','?')}/10 loc={technical.get('location_match','?')}/5 → A={bloque_a}/65 ({t_technical:.1f}s)")
            print(f"  HR        → signal={hr.get('apply_signal','?')} penalty={hr.get('penalty','?')} ({t_hr:.1f}s)")
            print(f"  SCORE: {score}/100 → {rating} | Total: {total_time:.1f}s")

    # Resumen final
    print(f"\n{'='*60}")
    print("RESUMEN COMPARATIVO")
    print(f"{'='*60}")
    header = f"{'Modelo':<25} " + " ".join([f"ID{oid:>3}" for oid in OFFER_IDS]) + "   AVG  T_tech"
    print(header)
    print("-" * len(header))
    for model in MODELS_TECHNICAL:
        scores = [r["score"] for r in results[model]]
        avg = sum(scores) // len(scores)
        t_avg = sum(r["t_technical"] for r in results[model]) / len(results[model])
        row = f"{model:<25} " + " ".join([f"{s:5d}" for s in scores]) + f"   {avg:3d}  {t_avg:.1f}s"
        print(row)

    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nResultados completos → benchmark_results.json")


if __name__ == "__main__":
    run_benchmark()
