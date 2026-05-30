"""
Test de evaluate.py con 5 ofertas seleccionadas manualmente.
Cubre: core falso (bloqueable), temporal estructural,
       core legítimo, stretch seniority, adjacent herramienta.

Orden: [348, 338, 336, 333, 313] — TRAGSA primero para validar bloqueos.
"""

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from src.db.init_db import get_connection
from src.pipeline.fetch import parse_skills_required
from src.utils.ollama_client import MODEL_HR, MODEL_TECHNICAL, ollama_call

from src.pipeline.evaluate import (
    load_perfil,
    load_skills_from_perfil,
    load_gap_from_perfil,
    load_experience_years_from_perfil,
    compute_skill_score,
    compute_experience_score,
    get_gap_multiplier,
    get_rating,
    evaluate_technical,
    evaluate_hr,
    evaluate_final,
    save_evaluation,
    update_evaluation_final,
    W_CORE, W_SEC, W_EXP, W_FIT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# TRAGSA falsa core → TRAGSA temporal → Rioglass core → COBSER stretch → NTT adjacent
TEST_IDS = [348, 338, 336, 333, 313]


def reset_test_offers(ids: list[int]) -> None:
    conn = get_connection()
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"DELETE FROM offer_evaluations WHERE offer_id IN ({placeholders})", ids
    )
    conn.execute(
        f"UPDATE offers SET is_evaluated=0 WHERE id IN ({placeholders})", ids
    )
    conn.commit()
    conn.close()
    log.info("Reset de evaluaciones para IDs: %s", ids)


def fetch_offers_by_id(ids: list[int]) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in ids)
    rows = cur.execute(
        f"""
        SELECT o.id, o.title, o.company_name, o.city, o.work_mode,
               o.description_clean, o.skills_required,
               o.relevance_flag, o.role_normalized,
               o.role_level_label,
               o.experience_min, o.experience_max,
               o.salary_min, o.salary_max, o.published_at,
               c.sector AS company_sector, c.size_range AS company_size
        FROM offers o
        LEFT JOIN companies c ON o.company_id = c.id
        WHERE o.id IN ({placeholders})
        ORDER BY o.id
        """,
        ids
    ).fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def run():
    reset_test_offers(TEST_IDS)

    perfil = load_perfil()
    offers = fetch_offers_by_id(TEST_IDS)
    candidate_skills_list = load_skills_from_perfil(perfil)
    candidate_skills_map = {s["name"]: s["level"] for s in candidate_skills_list}
    employment_gap = load_gap_from_perfil(perfil)
    candidate_years = load_experience_years_from_perfil(perfil)

    log.info("=" * 75)
    log.info("TEST: evaluate.py — 5 ofertas (con fix candidate_years)")
    log.info(f"Candidato: {len(candidate_skills_map)} skills, gap={employment_gap}años, exp={candidate_years}años")
    log.info(f"Skills: {candidate_skills_map}")
    log.info("=" * 75)

    stats = {"evaluated": 0, "errors": 0, "scores": [], "results": []}

    for offer in offers:
        t0 = time.monotonic()
        log.info("─" * 75)
        log.info(f"[{offer['id']}] {offer['title']} | {offer['company_name']}")
        log.info(f"    Flag: {offer['relevance_flag']} | Role: {offer['role_normalized']} | Level: {offer['role_level_label']}")

        try:
            # Paso 1: LLM detecta presencia de skills
            log.info("  Step 1: technical LLM (think=False)...")
            technical_llm = evaluate_technical(offer, candidate_skills_map)

            enriched_map = dict(candidate_skills_map)
            for sk in technical_llm.get("skills_present", []):
                if sk.get("present") and sk.get("candidate_level"):
                    enriched_map[sk["name"].lower()] = sk["candidate_level"]

            # Paso 2: Python calcula M_core, M_sec
            offer_skills = parse_skills_required(offer.get("skills_required"))
            M_core, M_sec, skill_detail = compute_skill_score(
                offer_skills, enriched_map,
                role_level_label=offer.get("role_level_label"),
            )
            log.info(f"  Step 2: M_core={M_core:.4f}  M_sec={M_sec:.4f}")

            # Paso 3: Python calcula F_exp
            F_exp = compute_experience_score(
                offer.get("experience_min"), candidate_years, employment_gap,
            )
            G = get_gap_multiplier(employment_gap)
            gap_severity = "low" if G >= 0.85 else ("medium" if G >= 0.55 else "high")
            req_exp = max(int(offer.get("experience_min") or 0), 0)
            log.info(f"  Step 3: F_exp={F_exp:.4f} (req={req_exp}y, cand={candidate_years:.1f}y, G={G}, sev={gap_severity})")

            # Paso 4: LLM HR
            log.info("  Step 4: HR LLM (think=True)...")
            hr = evaluate_hr(
                offer, perfil, skill_detail, M_core, M_sec, F_exp,
                employment_gap, gap_severity,
                offer.get("company_sector"), offer.get("company_size"),
            )
            if not hr:
                log.warning("  ❌ Sin resultado HR")
                stats["errors"] += 1
                continue
            F_fit = min(max(float(hr.get("context_fit", 0.5)), 0.0), 1.0)
            log.info(f"  Step 4: F_fit={F_fit:.4f} | env={hr.get('environment_compatibility')} | signal={hr.get('apply_signal')}")

            # Paso 5: Score final
            final_score = round(
                min(max(
                    W_CORE * M_core + W_SEC * M_sec + W_EXP * F_exp + W_FIT * F_fit,
                    0.0
                ), 1.0), 4
            )
            recommendation = get_rating(final_score)
            log.info(f"  Step 5: Score={final_score:.4f} → {recommendation}")
            log.info(f"    Desglose: core={W_CORE*M_core:.4f} + sec={W_SEC*M_sec:.4f} + exp={W_EXP*F_exp:.4f} + fit={W_FIT*F_fit:.4f}")

            ms = int((time.monotonic() - t0) * 1000)

            # Guardado parcial (Step 1-5, sin final validation)
            save_evaluation(
                offer["id"], technical_llm, hr, None, skill_detail,
                M_core, M_sec, F_exp, F_fit, final_score, recommendation, ms,
                partial=True,
            )

            # Paso 6: Validación final
            log.info("  Step 6: Final LLM (think=True)...")
            final = evaluate_final(offer, perfil, skill_detail, hr, final_score)
            if not final:
                log.warning("  ❌ Sin resultado final — evaluación parcial guardada")
                stats["errors"] += 1
                continue

            update_evaluation_final(offer["id"], final)

            block = final.get("apply_block")
            rec_final = final.get("apply_recommendation")
            val = final.get("relevance_validation")
            verdict = final.get("verdict", "")
            log.info(f"  ✅ Score={final_score:.4f} ({recommendation}) | block={block} | rec={rec_final} | val={val}")
            log.info(f"     Veredicto: {verdict[:200]}")
            stats["evaluated"] += 1
            stats["scores"].append(final_score)
            stats["results"].append({
                "id": offer["id"],
                "title": offer["title"],
                "company": offer["company_name"],
                "flag": offer["relevance_flag"],
                "score": final_score,
                "rating": recommendation,
                "M_core": M_core,
                "M_sec": M_sec,
                "F_exp": F_exp,
                "F_fit": F_fit,
                "apply_block": block,
                "apply_block_reason": final.get("apply_block_reason"),
                "apply_recommendation": rec_final,
                "relevance_validation": val,
                "relevance_corrected": final.get("relevance_corrected"),
                "apply_signal": hr.get("apply_signal"),
                "processing_ms": ms,
                "verdict": verdict,
                "hr_concerns": hr.get("hr_concerns", []),
                "strengths": hr.get("strengths", []),
                "red_flags": hr.get("red_flags", []),
                "interview_prep": hr.get("interview_prep", []),
            })

        except Exception as e:
            log.error(f"  ❌ Error: {e}", exc_info=True)
            stats["errors"] += 1

    log.info("=" * 75)
    log.info("RESUMEN FINAL")
    log.info(f"  Evaluadas: {stats['evaluated']} | Errores: {stats['errors']}")
    for r in stats["results"]:
        block_fmt = f" BLOCK={r['apply_block']}" if r["apply_block"] else ""
        log.info(f"  [{r['id']:>3}] {r['flag']:<10} score={r['score']:.4f} {r['rating']:<25} {r['company']:<25}{block_fmt}")
    if stats["scores"]:
        log.info(f"  Score promedio: {sum(stats['scores'])/len(stats['scores']):.4f}")
    log.info("=" * 75)

    out = Path("reports/testing/evaluate_5_test_results.json")
    out.write_text(json.dumps(stats["results"], ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Resultados guardados en {out}")
    return stats


if __name__ == "__main__":
    run()
