-- Job Intelligence Agent — esquema completo
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- companies ANTES de offers (FK dependency)
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    infojobs_company_id TEXT UNIQUE,
    name TEXT NOT NULL,
    sector TEXT,
    size_range TEXT,
    rating_overall REAL,
    rating_worklife REAL,
    rating_culture REAL,
    rating_growth REAL,
    reviews_count INTEGER DEFAULT 0,
    reviews_sample TEXT,
    avg_inscriptions INTEGER,
    offers_published_30d INTEGER,
    response_rate_signal TEXT DEFAULT 'desconocida',
    llm_description TEXT,
    green_flags TEXT,
    red_flags TEXT,
    llm_confidence TEXT,
    enriched_by_llm_at DATETIME,
    llm_model TEXT,
    first_seen_at DATETIME NOT NULL DEFAULT (datetime('now')),
    last_updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);

-- cv_versions para tracking de versiones de CV
CREATE TABLE IF NOT EXISTS cv_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    filename TEXT,
    uploaded_at DATETIME NOT NULL DEFAULT (datetime('now')),
    content_parsed TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Registro inmutable de cada item devuelto por Apify
-- append-only: el payload nunca se modifica tras la inserción
CREATE TABLE IF NOT EXISTS apify_raw_responses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    item_index   INTEGER NOT NULL,
    source_id    TEXT,
    fetched_at   DATETIME NOT NULL DEFAULT (datetime('now')),
    payload      TEXT NOT NULL,
    processed    INTEGER NOT NULL DEFAULT 0,
    error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_apify_raw_run_id    ON apify_raw_responses(run_id);
CREATE INDEX IF NOT EXISTS idx_apify_raw_source_id ON apify_raw_responses(source_id);
CREATE INDEX IF NOT EXISTS idx_apify_raw_processed ON apify_raw_responses(processed);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'infojobs',
    url TEXT,
    title TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
    employer_id TEXT,
    province TEXT,
    city TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_period TEXT,
    contract_type TEXT,
    work_mode TEXT,
    experience_min INTEGER,
    experience_max INTEGER,
    education_level TEXT,
    skills_required TEXT,
    description_raw TEXT,
    description_clean TEXT,
    applications_count INTEGER DEFAULT 0,
    views_count INTEGER DEFAULT 0,
    published_at DATETIME,
    expires_at DATETIME,
    fetched_at DATETIME NOT NULL DEFAULT (datetime('now')),
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1,
    is_evaluated INTEGER NOT NULL DEFAULT 0,
    search_layer INTEGER,
    role_level INTEGER,
    role_level_label TEXT,
    relevance_flag TEXT,
    raw_data TEXT,
    enriched_at TEXT,
    role_normalized TEXT,
    classification_reasoning TEXT,
    gap_type TEXT,
    role_reasoning TEXT,
    is_new_role INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_offers_source_id ON offers(source_id);
CREATE INDEX IF NOT EXISTS idx_offers_fetched_at ON offers(fetched_at);
CREATE INDEX IF NOT EXISTS idx_offers_is_active ON offers(is_active);
CREATE INDEX IF NOT EXISTS idx_offers_employer_id ON offers(employer_id);

CREATE TABLE IF NOT EXISTS offer_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    cv_version_id INTEGER REFERENCES cv_versions(id),
    evaluated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    skills_hard_match INTEGER,
    experience_match INTEGER,
    location_match INTEGER,
    market_competitiveness INTEGER,
    scoring_detail TEXT,
    match_score INTEGER,
    recommendation TEXT,
    environment_compatibility TEXT,
    hr_concerns TEXT,
    strengths TEXT,
    red_flags TEXT,
    gemma_verdict TEXT,
    interview_prep TEXT,
    apply_recommendation TEXT,
    descarte_tipo TEXT DEFAULT 'ninguno',
    descarte_razon TEXT,
    relevance_validation TEXT,
    relevance_corrected TEXT,
    relevance_reasoning TEXT,
    apply_block TEXT,
    apply_block_reason TEXT,
    llm_apply_signal TEXT,
    model_technical TEXT DEFAULT 'gemma4:e4b',
    model_hr TEXT DEFAULT 'gemma4:e4b',
    processing_ms INTEGER,
    sent_via_telegram INTEGER DEFAULT 0,
    sent_at DATETIME,
    daily_position INTEGER
);
CREATE INDEX IF NOT EXISTS idx_evaluations_offer_id ON offer_evaluations(offer_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_match_score ON offer_evaluations(match_score);
CREATE INDEX IF NOT EXISTS idx_evaluations_evaluated_at ON offer_evaluations(evaluated_at);

CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at DATETIME NOT NULL DEFAULT (datetime('now')),
    query_params TEXT,
    offers_fetched INTEGER DEFAULT 0,
    new_offers INTEGER DEFAULT 0,
    evaluated INTEGER DEFAULT 0,
    errors TEXT,
    duration_ms INTEGER,
    status TEXT DEFAULT 'ok'
);

CREATE TABLE IF NOT EXISTS market_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start DATE NOT NULL UNIQUE,
    calculated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    total_offers_compatible INTEGER,
    new_offers_this_week INTEGER,
    avg_offers_per_day REAL,
    avg_inscriptions_junior INTEGER,
    inscriptions_trend TEXT,
    top_skills_week TEXT,
    emerging_skills TEXT,
    avg_salary_junior REAL,
    salary_trend TEXT,
    pct_remote REAL,
    pct_hybrid REAL,
    pct_onsite REAL,
    market_temperature TEXT,
    weekly_summary TEXT
);

CREATE TABLE IF NOT EXISTS strategic_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    trigger_type TEXT NOT NULL,
    insight_text TEXT NOT NULL,
    data_snapshot TEXT,
    action_suggested TEXT,
    sent_telegram INTEGER DEFAULT 0,
    user_acted INTEGER DEFAULT 0,
    outcome_notes TEXT
);

CREATE TABLE IF NOT EXISTS user_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    offer_id        INTEGER REFERENCES offers(id),
    feedback_type   TEXT NOT NULL,
    raw_text        TEXT NOT NULL,
    processed       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_psychology (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
    last_updated    DATETIME NOT NULL DEFAULT (datetime('now')),
    raw_feedback    TEXT,
    summary         TEXT,
    key_insights    TEXT,
    version         INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS search_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    cv_version_id INTEGER REFERENCES cv_versions(id),
    geo_hierarchy TEXT,
    role_hierarchy TEXT,
    active_geo_level INTEGER,
    active_role_level INTEGER,
    last_full_fetch DATETIME,
    last_updated DATETIME NOT NULL DEFAULT (datetime('now')),
    role_catalog TEXT
);

CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    send_time TEXT DEFAULT '09:00',
    max_offers_day INTEGER DEFAULT 3,
    send_mode TEXT DEFAULT 'morning',
    min_score_send INTEGER DEFAULT 35,
    weekly_summary INTEGER DEFAULT 1,
    strategic_alerts INTEGER DEFAULT 1
);