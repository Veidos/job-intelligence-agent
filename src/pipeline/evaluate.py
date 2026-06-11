"""
Pipeline: evaluación de ofertas con gemma4:e4b (técnico y HR).
Procesa ofertas clasificadas (relevance_flag NOT NULL, is_evaluated=0).
Incluye evaluación técnica, HR y validación final (relevance + bloqueos).
PERFIL.md es la única fuente de verdad del candidato.
"""

import json
import logging
import sys
import time
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from src.db.init_db import get_connection  # noqa: E402
from src.pipeline.fetch import parse_skills_required  # noqa: E402
from src.utils.ollama_client import MODEL_HR, MODEL_TECHNICAL, ollama_call  # noqa: E402

log = logging.getLogger(__name__)


def _clamp(val, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(val or 0)))


def load_skills_from_perfil(perfil: str) -> list[dict]:
    """Parsea skills con nivel desde PERFIL.md.

    Incluye tanto las skills técnicas explícitas como las titulaciones
    académicas de ## Educación (como skills de nivel "avanzado").
    """
    import re

    skills = []

    # --- Skills técnicas desde ## Skills técnicas ---
    match = re.search(r"## Skills técnicas\s*\n((?:- .*\n?)+)", perfil, re.IGNORECASE)
    if match:
        skills_block = match.group(1)
        skill_pattern = re.compile(
            r"- \*\*([^(]+)\((\w+)\)\*\*:?\s*(.+)?", re.IGNORECASE
        )

        for line in skills_block.strip().split("\n"):
            line = line.strip()
            if not line.startswith("-"):
                continue
            m = skill_pattern.match(line)
            if m:
                name = m.group(1).strip()
                level = m.group(2).strip().lower()
                evidence = m.group(3).strip() if m.group(3) else ""
                skills.append({"name": name, "level": level, "evidence": evidence})
            else:
                clean = line.lstrip("- ").strip()
                if clean:
                    skills.append(
                        {
                            "name": clean,
                            "level": "básico",
                            "evidence": "sin información de nivel",
                        }
                    )

    # --- Titulaciones académicas desde ## Educación ---
    edu_sec = re.search(r"## Educación\s*\n(.*?)(?=\n##[^#]|\Z)", perfil, re.DOTALL)
    if edu_sec:
        edu_pattern = re.compile(r"- \*\*([^*]+)\*\*")
        existing_names = {s["name"].lower() for s in skills}
        for line in edu_sec.group(1).strip().split("\n"):
            m = edu_pattern.match(line.strip())
            if m:
                title = m.group(1).strip()
                if title.lower() not in existing_names:
                    skills.append(
                        {
                            "name": title,
                            "level": "avanzado",
                            "evidence": "formación académica",
                        }
                    )
                    existing_names.add(title.lower())

    return skills


def load_gap_from_perfil(perfil: str) -> float | None:
    """Extrae employment_gap_years desde PERFIL.md.

    Formato esperado:
    ## Gap de empleo
    - **Años:** 3.5
    """
    import re

    # Buscar sección de gap
    gap_match = re.search(r"## Gap de empleo\s*\n((?:.+\n?)+)", perfil, re.IGNORECASE)
    if not gap_match:
        return None

    gap_block = gap_match.group(1)

    # Buscar patrón: - **Años:** 3.5
    years_match = re.search(r"- \*\*Años:\*\*\s*([\d.]+)", gap_block)
    if years_match:
        try:
            return float(years_match.group(1))
        except ValueError:
            pass
    return None


def load_location_from_perfil(perfil: str) -> str:
    """Extrae ubicación actual del candidato desde PERFIL.md.

    Formato esperado:
    - **Ubicación actual:** Jerez de la Frontera, Spain
    """
    import re

    m = re.search(r"\*\*Ubicación actual:\*\*\s*(.+)", perfil, re.IGNORECASE)
    return m.group(1).strip() if m else ""


MONTH_NAMES: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "ene": 1,
    "abr": 4,
    "ago": 8,
    "dic": 12,
}


def _month_from_name(name: str) -> int | None:
    return MONTH_NAMES.get(name.lower().strip()[:3])


def load_experience_years_from_perfil(perfil: str) -> float:
    """Extrae años totales de experiencia profesional del candidato desde PERFIL.md.

    Fallback 1: busca mención explícita "X años de experiencia".
    Fallback 2: parsea fechas en la sección ## Experiencia y calcula el span
                (desde la fecha más temprana hasta la más reciente).
    Fallback final: 0.0 si no se encuentra.
    """
    import re

    # Fallback 1 — mención explícita
    m = re.search(
        r"(?:años?.*experiencia|experiencia.*años?).*?([\d.]+)", perfil, re.IGNORECASE
    )
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Fallback 2 — span desde duraciones en ## Experiencia
    sec = re.search(r"## Experiencia\s*\n(.*?)(?=\n##[^#]|\Z)", perfil, re.DOTALL)
    if not sec:
        return 0.0

    dates = re.findall(
        r"\*\*Duración:\*\*\s*(\w+)\s+(\d{4})\s*[–\-]\s*(\w+)\s+(\d{4})",
        sec.group(1),
        re.IGNORECASE,
    )
    if not dates:
        return 0.0

    all_months: list[int] = []
    for sm, sy, em, ey in dates:
        sm_i = _month_from_name(sm)
        em_i = _month_from_name(em)
        if sm_i is not None and em_i is not None:
            all_months.append(int(sy) * 12 + sm_i)
            all_months.append(int(ey) * 12 + em_i)

    if not all_months:
        return 0.0

    span_months = max(all_months) - min(all_months)
    return round(span_months / 12, 1)


# G(gap): multiplicador por años de gap laboral — tabla fija, no LLM
GAP_MULTIPLIER: list[tuple[float, float, float]] = [
    # (gap_min, gap_max_excl, multiplier)
    (0.0, 1.0, 1.00),
    (1.0, 2.0, 0.85),
    (2.0, 3.0, 0.70),
    (3.0, 4.0, 0.55),
    (4.0, float("inf"), 0.40),
]

# Score final 0-1
RATING = [
    (0.75, 1.01, "Prioritario"),
    (0.55, 0.75, "Aplicar"),
    (0.35, 0.55, "Con expectativas bajas"),
    (0.00, 0.35, "No aplicar"),
]

# Pesos del score final  S = W_CORE*M_core + W_SEC*M_sec + W_EXP*F_exp + W_FIT*F_fit
W_CORE = 0.45
W_SEC = 0.15
W_EXP = 0.25
W_FIT = 0.15


def get_gap_multiplier(gap_years: float | None) -> float:
    if gap_years is None:
        return 1.0
    for lo, hi, mult in GAP_MULTIPLIER:
        if lo <= gap_years < hi:
            return mult
    return 0.40


def compute_skill_score(
    offer_skills: dict,
    candidate_skills_map: dict[str, str],
) -> tuple[float, float, dict]:
    """Calcula M_core y M_sec.

    L es binario: 1.0 si el candidato tiene la skill, 0.0 si no.
    Sin diferenciación por nivel — la profundidad la captura F_exp
    mediante experience_min del scraper.

    Returns: (M_core, M_sec, skill_detail)
    skill_detail tiene los cálculos intermedios para trazabilidad.
    """

    def _score_list(skill_list: list[dict]) -> tuple[float, list]:
        if not skill_list:
            return 0.0, []
        scores = []
        detail = []
        for sk in skill_list:
            name = (sk.get("name") or "").strip()
            cand_level = None
            name_lower = name.lower()
            for cand_name, cand_lv in candidate_skills_map.items():
                if name_lower in cand_name.lower() or cand_name.lower() in name_lower:
                    cand_level = cand_lv
                    break
            present = cand_level is not None
            L = 1.0 if present else 0.0
            scores.append(L)
            detail.append(
                {
                    "skill": name,
                    "candidate_level": cand_level,
                    "present": present,
                    "L": 1.0 if present else 0.0,
                }
            )
        return sum(scores) / len(scores), detail

    M_core, core_detail = _score_list(offer_skills.get("core") or [])
    M_sec, sec_detail = _score_list(offer_skills.get("secondary") or [])

    return (
        round(M_core, 4),
        round(M_sec, 4),
        {"core": core_detail, "secondary": sec_detail},
    )


def compute_experience_score(
    experience_min: int | None,
    candidate_years: float,
) -> float:
    """F_exp = years_match (sin gap — el gap es contexto cualitativo HR).

    Si experience_min == 0 → years_match = 1.0.
    """
    req = max(int(experience_min or 0), 0)
    years_match = 1.0 if req == 0 else min(candidate_years / req, 1.0)
    return round(years_match, 4)


def compute_location_score(
    work_mode: str | None,
    candidate_city: str,
    offer_city: str | None,
) -> float:
    """Location_match determinista basado en modalidad y ciudad.

    | Condición | Score |
    |---|---|
    | Solo teletrabajo | 1.0 |
    | Híbrido | 0.7 |
    | Presencial, misma ciudad | 0.5 |
    | Presencial, ciudad distinta | 0.2 |
    | Sin datos | 0.5 (neutral) |
    """
    mode = (work_mode or "").strip().lower()
    if mode == "solo teletrabajo":
        return 1.0
    if mode == "híbrido" or mode == "hibrido":
        return 0.7
    if not candidate_city or not offer_city:
        return 0.5
    if (
        candidate_city.lower() in offer_city.lower()
        or offer_city.lower() in candidate_city.lower()
    ):
        return 0.5
    return 0.2


def get_rating(score: float) -> str:
    for lo, hi, label in RATING:
        if lo <= score < hi:
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
        SELECT o.id, o.title, o.company_name, o.city, o.work_mode,
               o.description_clean, o.skills_required,
               o.relevance_flag, o.role_normalized,
               o.experience_min,
               o.salary_min, o.salary_max, o.published_at,
               c.sector AS company_sector, c.size_range AS company_size
        FROM offers o
        LEFT JOIN companies c ON o.company_id = c.id
        WHERE o.relevance_flag IS NOT NULL
          AND o.is_evaluated = 0
        ORDER BY o.published_at DESC
        LIMIT ?
    """,
        (limit,),
    ).fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def evaluate_technical(
    offer: dict,
    candidate_skills_map: dict[str, str],
) -> dict:
    """El LLM solo detecta presencia de skills y nivel del candidato.

    No devuelve puntuaciones — eso lo hace Python con compute_skill_score.
    Retorna:
    {
      "skills_present": [
        {"name": str, "candidate_level": "basico|intermedio|avanzado|null", "present": bool},
        ...
      ],
      "reasoning": str
    }
    """
    skills_raw = offer.get("skills_required") or "{}"
    offer_skills = parse_skills_required(skills_raw)

    all_skill_names = [s["name"] for s in offer_skills.get("core", [])] + [
        s["name"] for s in offer_skills.get("secondary", [])
    ]

    if not all_skill_names:
        return {"skills_present": [], "reasoning": "sin skills estructuradas en oferta"}

    candidate_skills_formatted = (
        "\n".join(
            f"  - {name}: {level}" for name, level in candidate_skills_map.items()
        )
        or "  (sin skills registradas)"
    )

    prompt = f"""Para cada skill de la oferta, indica si el candidato la tiene y a qué nivel.

SKILLS DEL CANDIDATO:
{candidate_skills_formatted}

SKILLS QUE PIDE LA OFERTA (debes evaluar TODAS):
{json.dumps(all_skill_names, ensure_ascii=False)}

Reglas:
- present=true solo si la skill (o una equivalente directa) está en el listado del candidato
- candidate_level: el nivel del candidato para esa skill, o null si no la tiene
- No inventes skills ni niveles. Si no está, present=false y candidate_level=null.
- Equivalencias válidas: "machine learning" ↔ "ML", "scikit-learn" ↔ "sklearn", etc.

Responde SOLO este JSON:
{{
  "skills_present": [
    {{"name": "<skill>", "present": <true|false>, "candidate_level": "<basico|intermedio|avanzado|null>"}},
    ...
  ],
  "reasoning": "<una frase sobre el match global>"
}}"""

    result = ollama_call(
        model=MODEL_TECHNICAL,
        prompt=prompt,
        expect_json=True,
        temperature=0.0,
        think=False,
    )
    return result if isinstance(result, dict) else {}


def evaluate_hr(
    offer: dict,
    perfil: str,
    skill_detail: dict,
    M_core: float,
    M_sec: float,
    F_exp: float,
    employment_gap: float | None = None,
    gap_severity: str = "low",
    company_sector: str | None = None,
    company_size: str | None = None,
) -> dict:
    """Evalúa fit de contexto (F_fit) y genera análisis cualitativo.

    El único número que devuelve es context_fit (0.0-1.0).
    gap_severity: low|medium|high — calculado fuera, pasado como contexto.
    """
    prompt = f"""Eres un recruiter senior. Tienes ya el análisis técnico de esta candidatura.
Tu tarea: evaluar el fit de contexto y generar análisis cualitativo honesto.

SCORES TÉCNICOS (ya calculados, NO los recalcules):
- Match skills core: {M_core:.0%}
- Match skills secundarias: {M_sec:.0%}
- Fit de experiencia: {F_exp:.0%}
- Gap laboral: {employment_gap or 0:.1f} años (severidad: {gap_severity})

DETALLE DE SKILLS:
{json.dumps(skill_detail, ensure_ascii=False, indent=2)[:1500]}

PERFIL DEL CANDIDATO:
{perfil[:2500]}

OFERTA:
Título: {offer["title"]} | Empresa: {offer["company_name"]}
Sector empresa: {company_sector or "desconocido"} | Tamaño: {company_size or "desconocido"}
Ubicación: {offer.get("city")} | Modalidad: {offer.get("work_mode")}
Descripción: {(offer.get("description_clean") or "")[:1200]}

EVALÚA el context_fit (0.0-1.0) considerando SOLO:
- ¿La cultura/sector de la empresa es compatible con el perfil del candidato?
- ¿La modalidad y ubicación son viables?
- ¿El perfil personal (motivación, reconversión, TDAH) encaja con el entorno laboral?
- ¿La empresa suele contratar perfiles de reconversión para este tipo de rol?

NO penalices el gap ni las skills — eso ya está capturado en los scores técnicos.

Devuelve SOLO este JSON:
{{
  "context_fit": <float 0.0-1.0>,
  "environment_compatibility": "<alta|media|baja>",
  "strengths": ["<punto fuerte concreto y específico para esta oferta>"],
  "red_flags": ["<bandera roja concreta>"],
  "hr_concerns": ["<preocupación del recruiter>"],
  "interview_prep": ["<consejo concreto y específico para esta oferta, no genérico>"],
  "gap_severity": "<low|medium|high>",
  "apply_signal": "<yes|no|maybe>",
  "verdict": "<síntesis en 2-3 frases, específica para esta oferta, no para el perfil general>"
}}"""

    result = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
        temperature=0.0,
        think=True,
    )
    return result if isinstance(result, dict) else {}


def evaluate_final(
    offer: dict,
    perfil: str,
    skill_detail: dict,
    hr: dict,
    final_score: float,
) -> dict:
    """Tercer prompt: valida relevance_flag y detecta bloqueos reales."""
    prompt = f"""Eres un evaluador senior. Tienes el análisis completo de esta candidatura.

PERFIL DEL CANDIDATO:
{perfil[:2000]}

OFERTA:
Título: {offer["title"]}
Empresa: {offer.get("company_name", "")} | Sector: {offer.get("company_sector") or "desconocido"}
Ciudad: {offer.get("city", "")} | Modalidad: {offer.get("work_mode", "")}
Descripción: {(offer.get("description_clean") or "")[:1800]}

CLASIFICACIÓN PREVIA: relevance_flag={offer.get("relevance_flag")} | role={offer.get("role_normalized")}
SCORE FINAL: {final_score:.2f} / 1.0
DETALLE SKILLS: {json.dumps(skill_detail, ensure_ascii=False)[:800]}
VEREDICTO HR: {hr.get("verdict", "")}

TAREA 1 — VALIDAR relevance_flag:
¿El classifier asignó correctamente "{offer.get("relevance_flag")}"?
Ahora tienes la descripción completa. Confirma o corrige.

TAREA 2 — DETECTAR BLOQUEOS REALES:
Bloqueo real = requisito que hace inviable la candidatura independientemente del score.
Ejemplos: convenio prácticas universitarias, certificado discapacidad obligatorio,
nacionalidad legal, titulación académica obligatoria que el candidato no posee.
NO son bloqueos: falta de experiencia, skills no dominadas, gap laboral.

Responde SOLO este JSON:
{{
  "relevance_validation": "<confirmed|corrected>",
  "relevance_corrected": <"core"|"adjacent"|"stretch"|"temporal"|null>,
  "relevance_reasoning": "<una frase>",
  "apply_block": <"requisito_imposible"|"practicas"|"otro"|null>,
  "apply_block_reason": <"<texto>"|null>,
  "apply_recommendation": "<yes|maybe|no>",
  "verdict": "<síntesis ejecutiva en 2-3 frases, específica para esta oferta>"
}}"""

    result = ollama_call(
        model=MODEL_HR,
        prompt=prompt,
        expect_json=True,
        temperature=0.0,
        think=True,
    )
    return result if isinstance(result, dict) else {}


def _build_evaluation_params(
    offer_id: int,
    hr: dict,
    final: dict | None,
    skill_detail: dict,
    M_core: float,
    M_sec: float,
    F_exp: float,
    F_fit: float,
    location_match: float,
    final_score: float,
    recommendation: str,
    processing_ms: int,
) -> tuple:
    final_dict = final or {}
    return (
        offer_id,
        None,
        round(M_core * 100),
        round(F_exp * 100),
        round(location_match * 100),
        round(F_fit * 100),
        json.dumps(
            {
                "M_core": round(M_core, 4),
                "M_sec": round(M_sec, 4),
                "F_exp": round(F_exp, 4),
                "F_fit": round(F_fit, 4),
                "weights": {
                    "W_CORE": W_CORE,
                    "W_SEC": W_SEC,
                    "W_EXP": W_EXP,
                    "W_FIT": W_FIT,
                },
                "skill_detail": skill_detail,
            },
            ensure_ascii=False,
        ),
        round(final_score * 100),
        recommendation,
        hr.get("environment_compatibility"),
        json.dumps(hr.get("hr_concerns", []), ensure_ascii=False),
        json.dumps(hr.get("strengths", []), ensure_ascii=False),
        json.dumps(hr.get("red_flags", []), ensure_ascii=False),
        hr.get("verdict", ""),
        recommendation,
        processing_ms,
        MODEL_TECHNICAL,
        MODEL_HR,
        json.dumps(hr.get("interview_prep", []), ensure_ascii=False),
        final_dict.get("relevance_validation"),
        final_dict.get("relevance_corrected"),
        final_dict.get("relevance_reasoning"),
        final_dict.get("apply_block"),
        final_dict.get("apply_block_reason"),
        final_dict.get("apply_recommendation"),
    )


_COLUMNS = (
    "offer_id, cv_version_id, "
    "skills_hard_match, experience_match, "
    "location_match, "
    "market_competitiveness, scoring_detail, "
    "match_score, recommendation, "
    "environment_compatibility, hr_concerns, "
    "strengths, red_flags, gemma_verdict, "
    "apply_recommendation, processing_ms, "
    "model_technical, model_hr, "
    "interview_prep, "
    "relevance_validation, relevance_corrected, relevance_reasoning, "
    "apply_block, apply_block_reason, llm_apply_signal"
)

_SET_CLAUSE = (
    "skills_hard_match=?, experience_match=?, "
    "location_match=?, "
    "market_competitiveness=?, scoring_detail=?, "
    "match_score=?, recommendation=?, "
    "environment_compatibility=?, hr_concerns=?, "
    "strengths=?, red_flags=?, gemma_verdict=?, "
    "apply_recommendation=?, processing_ms=?, "
    "model_technical=?, model_hr=?, "
    "interview_prep=?, "
    "relevance_validation=?, relevance_corrected=?, relevance_reasoning=?, "
    "apply_block=?, apply_block_reason=?, llm_apply_signal=?"
)


def save_evaluation(
    offer_id: int,
    technical_llm: dict,
    hr: dict,
    final: dict | None,
    skill_detail: dict,
    M_core: float,
    M_sec: float,
    F_exp: float,
    F_fit: float,
    location_match: float,
    final_score: float,
    recommendation: str,
    processing_ms: int,
    partial: bool = False,
) -> None:
    conn = get_connection()
    cur = conn.cursor()

    params = _build_evaluation_params(
        offer_id,
        hr,
        final,
        skill_detail,
        M_core,
        M_sec,
        F_exp,
        F_fit,
        location_match,
        final_score,
        recommendation,
        processing_ms,
    )

    existing = cur.execute(
        "SELECT id FROM offer_evaluations WHERE offer_id = ?", (offer_id,)
    ).fetchone()

    if existing:
        cur.execute(
            f"UPDATE offer_evaluations SET {_SET_CLAUSE} WHERE offer_id = ?",
            params[1:] + (offer_id,),
        )
    else:
        ncols = len(params)
        cur.execute(
            f"INSERT INTO offer_evaluations ({_COLUMNS}) VALUES ({','.join(['?'] * ncols)})",
            params,
        )

    if not partial:
        cur.execute("UPDATE offers SET is_evaluated=1 WHERE id=?", (offer_id,))

    conn.commit()
    conn.close()


def _normalize_none(val):
    """Convierte string 'null'/'None' (típico error del LLM) a Python None."""
    if isinstance(val, str) and val.strip().lower() in ("null", "none"):
        return None
    return val


def update_evaluation_final(offer_id: int, final: dict) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE offer_evaluations SET
            relevance_validation = ?, relevance_corrected = ?,
            relevance_reasoning = ?, apply_block = ?,
            apply_block_reason = ?, llm_apply_signal = ?,
            gemma_verdict = ?
         WHERE offer_id = ?""",
        (
            final.get("relevance_validation"),
            final.get("relevance_corrected"),
            final.get("relevance_reasoning"),
            _normalize_none(final.get("apply_block")),
            _normalize_none(final.get("apply_block_reason")),
            final.get("apply_recommendation"),
            final.get("verdict", ""),
            offer_id,
        ),
    )
    cur.execute("UPDATE offers SET is_evaluated=1 WHERE id=?", (offer_id,))
    conn.commit()
    conn.close()


def run_evaluate(limit: int = 10) -> dict:
    perfil = load_perfil()
    offers = get_pending_offers(limit)
    candidate_skills_map = load_skills_from_perfil(perfil)
    employment_gap = load_gap_from_perfil(perfil)
    candidate_years = load_experience_years_from_perfil(perfil)
    candidate_city = load_location_from_perfil(perfil)

    # Convertir load_skills_from_perfil (list[dict]) a dict[str, str]
    candidate_skills_map = {s["name"]: s["level"] for s in candidate_skills_map}

    log.info("Ofertas pendientes: %d", len(offers))
    log.info(
        "Skills candidato: %d | Gap: %s años | Exp: %.1f años | Ciudad: %s",
        len(candidate_skills_map),
        employment_gap,
        candidate_years,
        candidate_city,
    )

    stats = {"evaluated": 0, "errors": 0, "scores": [], "total": len(offers)}

    for idx, offer in enumerate(tqdm(offers, desc="Evaluando", unit="oferta"), 1):
        t0 = time.monotonic()
        try:
            log.debug("[%d/%d] Evaluando: %s", idx, len(offers), offer["title"])

            # Parsear skills de la oferta (backward-compat con legacy flat array)
            offer_skills = parse_skills_required(offer.get("skills_required"))

            # Paso 1: LLM detecta presencia de skills (sin inventar números)
            technical_llm = evaluate_technical(offer, candidate_skills_map)

            # Enriquecer map con equivalencias que el LLM detectó
            enriched_map = dict(candidate_skills_map)
            for sk in technical_llm.get("skills_present", []):
                if sk.get("present") and sk.get("candidate_level"):
                    enriched_map[sk["name"].lower()] = sk["candidate_level"]

            # Paso 2: Python calcula M_core y M_sec (L binario, sin role_level_label)
            M_core, M_sec, skill_detail = compute_skill_score(
                offer_skills,
                enriched_map,
            )

            # Paso 3: Python calcula F_exp (determinista, sin gap — es contexto HR)
            F_exp = compute_experience_score(
                offer.get("experience_min"),
                candidate_years,
            )

            # Location match determinista
            location_match = compute_location_score(
                offer.get("work_mode"),
                candidate_city,
                offer.get("city"),
            )

            # Severidad del gap para contexto HR
            G = get_gap_multiplier(employment_gap)
            gap_severity = "low" if G >= 0.85 else ("medium" if G >= 0.55 else "high")

            # Paso 4: LLM evalúa context_fit (F_fit)
            hr = evaluate_hr(
                offer,
                perfil,
                skill_detail,
                M_core,
                M_sec,
                F_exp,
                employment_gap,
                gap_severity,
                offer.get("company_sector"),
                offer.get("company_size"),
            )
            if not hr:
                log.warning("Sin resultado HR: %s", offer["title"])
                stats["errors"] += 1
                continue

            F_fit = min(max(float(hr.get("context_fit", 0.5)), 0.0), 1.0)

            # Paso 5: Score final determinista
            final_score = round(
                min(
                    max(
                        W_CORE * M_core + W_SEC * M_sec + W_EXP * F_exp + W_FIT * F_fit,
                        0.0,
                    ),
                    1.0,
                ),
                4,
            )
            recommendation = get_rating(final_score)

            ms = int((time.monotonic() - t0) * 1000)

            # Guardado parcial tras Step 5 (final validation pending)
            save_evaluation(
                offer["id"],
                technical_llm,
                hr,
                None,
                skill_detail,
                M_core,
                M_sec,
                F_exp,
                F_fit,
                location_match,
                final_score,
                recommendation,
                ms,
                partial=True,
            )

            # Paso 6: Validación final (relevance + bloqueos)
            final = evaluate_final(offer, perfil, skill_detail, hr, final_score)
            if not final:
                log.warning("Sin resultado final: %s", offer["title"])
                stats["errors"] += 1
                continue

            # Actualizar campos finales + marcar is_evaluated=1
            update_evaluation_final(offer["id"], final)

            block = _normalize_none(final.get("apply_block"))
            log.info(
                "✓ %s → %.2f (%s)%s",
                offer["title"],
                final_score,
                recommendation,
                f" [BLOQUEADO: {block}]" if block else "",
            )
            stats["evaluated"] += 1
            stats["scores"].append(final_score)

        except Exception as e:
            log.error("Error evaluando %s: %s", offer["title"], e)
            stats["errors"] += 1

    if stats["scores"]:
        stats["avg_score"] = round(sum(stats["scores"]) / len(stats["scores"]), 4)

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluar ofertas pendientes")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Número de ofertas a evaluar (0 = sin límite)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    limit = args.limit if args.limit > 0 else 1000
    stats = run_evaluate(limit=limit)
    log.info("Completado: %s", stats)
