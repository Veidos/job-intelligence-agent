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
    first_seen_at DATETIME NOT NULL DEFAULT (datetime('now')),
    last_updated_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);

-- cv_versions ANTES de candidate_profile (FK dependency)
CREATE TABLE IF NOT EXISTS cv_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL,
    filename TEXT,
    uploaded_at DATETIME NOT NULL DEFAULT (datetime('now')),
    content_parsed TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'infojobs',
    url TEXT,
    title TEXT NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    company_name TEXT,
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
    is_evaluated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_offers_source_id ON offers(source_id);
CREATE INDEX IF NOT EXISTS idx_offers_fetched_at ON offers(fetched_at);
CREATE INDEX IF NOT EXISTS idx_offers_is_active ON offers(is_active);

CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL DEFAULT '1.0',
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1,
    full_name TEXT,
    location_current TEXT,
    skills_technical TEXT,
    education TEXT,
    experience TEXT,
    languages TEXT,
    projects TEXT,
    employment_gap_years REAL,
    salary_min_viable REAL,
    location_preference TEXT,
    relocation_conditions TEXT,
    work_mode_preference TEXT,
    personal_concerns TEXT,
    environment_avoid_keywords TEXT,
    environment_prefer_keywords TEXT,
    min_score_to_recommend INTEGER DEFAULT 45,
    cv_version_id INTEGER REFERENCES cv_versions(id)
);

CREATE TABLE IF NOT EXISTS offer_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id INTEGER NOT NULL REFERENCES offers(id),
    cv_version_id INTEGER REFERENCES cv_versions(id),
    evaluated_at DATETIME NOT NULL DEFAULT (datetime('now')),
    skills_hard_match INTEGER,
    experience_match INTEGER,
    education_match INTEGER,
    location_match INTEGER,
    trajectory_coherence INTEGER,
    recency_relevance INTEGER,
    market_competitiveness INTEGER,
    penalty INTEGER DEFAULT 0,
    penalty_breakdown TEXT,
    match_score INTEGER,
    recommendation TEXT,
    company_fit_score INTEGER,
    environment_compatibility TEXT,
    company_red_flags TEXT,
    company_green_flags TEXT,
    hr_concerns TEXT,
    strengths TEXT,
    red_flags TEXT,
    gemma_verdict TEXT,
    apply_recommendation TEXT,
    model_technical TEXT DEFAULT 'qwen2.5-coder:7b',
    model_hr TEXT DEFAULT 'gemma4:e4b',
    processing_ms INTEGER,
    sent_via_telegram INTEGER DEFAULT 0,
    sent_at DATETIME
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
