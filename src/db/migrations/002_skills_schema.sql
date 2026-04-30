-- ============================================================
-- MIGRACIÓN 002 — Skills en 3NF
-- Tablas nuevas únicamente. No modifica offers ni datos existentes.
-- ============================================================

-- Catálogo maestro de skills
CREATE TABLE IF NOT EXISTS skills (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,   -- "SQL", "Power BI", "Python"
  category    TEXT,                   -- 'database'|'visualization'|'language'|'soft'|'domain'
  aliases     TEXT DEFAULT '[]',      -- JSON: ["sql", "structured query language"]
  created_at  DATETIME DEFAULT (datetime('now'))
);

-- Skills por oferta (junction)
CREATE TABLE IF NOT EXISTS offer_skills (
  id              INTEGER PRIMARY KEY,
  offer_id        INTEGER NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
  skill_id        INTEGER NOT NULL REFERENCES skills(id),
  importance      TEXT NOT NULL CHECK(importance IN ('pivot','required','nice_to_have')),
  level_required  TEXT CHECK(level_required IN ('básico','intermedio','avanzado','experto','cualquiera')),
  evidence_text   TEXT,               -- cita literal o frase que llevó a esta inferencia
  inferred_by     TEXT CHECK(inferred_by IN ('explicit','contextual')),
  created_at      DATETIME DEFAULT (datetime('now')),
  UNIQUE(offer_id, skill_id)
);

-- Skills actuales del candidato
CREATE TABLE IF NOT EXISTS candidate_skills (
  id              INTEGER PRIMARY KEY,
  skill_id        INTEGER NOT NULL REFERENCES skills(id) UNIQUE,
  level_current   TEXT CHECK(level_current IN ('básico','intermedio','avanzado','experto')),
  evidence        TEXT,               -- "proyecto inundaciones España", "DataCamp track"
  source          TEXT CHECK(source IN ('PERFIL.md','feedback','inferred')),
  updated_at      DATETIME DEFAULT (datetime('now'))
);

-- Patrones de evaluación aprendidos
CREATE TABLE IF NOT EXISTS evaluation_patterns (
  id              INTEGER PRIMARY KEY,
  pattern_type    TEXT NOT NULL,      -- 'experience_gap'|'pivot_missing'|'process_long'|'culture_mismatch'
  description     TEXT NOT NULL,      -- descripción legible del patrón
  score_impact    REAL,               -- impacto observado en score_final
  times_applied   INTEGER DEFAULT 0,
  user_confirmed  INTEGER DEFAULT 0,  -- nº de veces que /feedback validó el patrón
  created_at      DATETIME DEFAULT (datetime('now'))
);

-- Evaluaciones (historial completo, no sobreescribe)
CREATE TABLE IF NOT EXISTS evaluations (
  id                  INTEGER PRIMARY KEY,
  offer_id            INTEGER NOT NULL REFERENCES offers(id),
  evaluated_at        DATETIME DEFAULT (datetime('now')),
  score_raw           REAL,           -- score antes de strategic_review
  score_final         REAL,           -- score tras ajustes
  adjusted            INTEGER DEFAULT 0,
  adjustment_reason   TEXT,
  reasoning_match     TEXT,           -- qué vio gemma4 en el matching
  reasoning_strategy  TEXT,           -- qué vio gemma4 en strategic_review
  psychology_snapshot TEXT,           -- JSON snapshot de key_insights usados
  patterns_applied    TEXT,           -- JSON: IDs de evaluation_patterns usados
  model_version       TEXT            -- para detectar drift si cambias modelos
);

-- Índices de rendimiento
CREATE INDEX IF NOT EXISTS idx_offer_skills_offer  ON offer_skills(offer_id);
CREATE INDEX IF NOT EXISTS idx_offer_skills_skill  ON offer_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_offer_skills_importance ON offer_skills(importance);
CREATE INDEX IF NOT EXISTS idx_evaluations_offer   ON evaluations(offer_id);
CREATE INDEX IF NOT EXISTS idx_candidate_skills_skill ON candidate_skills(skill_id);
