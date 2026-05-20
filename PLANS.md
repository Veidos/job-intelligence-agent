# PLANS.md — Estado del Proyecto (Método Ledger)

## FASE 1 — Cimientos
  [x] init_db.py + schema.sql completo
  [x] ollama_client.py con reintentos y validación JSON
  [x] Test de conexión Telegram
  [x] Test de conexión Ollama (gemma4:e4b)
  [x] Test de conexión InfoJobs API (vía Apify)

## FASE 2 — Onboarding
  [x] cv_extractor.py (gemma4 → datos estructurados)
  [x] interviewer.py (gemma4 → preguntas secuenciales)
  [x] Generación de PERFIL.md (fuente única de verdad)
  [x] run.py orquesta el onboarding completo

## FASE 3 — Pipeline base
  [x] fetch.py (InfoJobs API → limpieza → upsert en DB)
  [x] evaluate.py (gemma4:e4b técnico + HR → offer_evaluations)
  [x] send.py (formato Telegram → envío)
  [x] run.py (orquestador del pipeline completo)
  [x] role_classifier.py (clasificación de ofertas y relevance_flag)
  [x] Añadir campos search_layer, role_level, relevance_flag a offers
  [x] Crear tabla search_config para configuración geográfica y de rol
  [x] Pre-filtro de requisitos impossibles (descartar 0/1)
  [x] fetch_company.py — enriquecimiento de companies desde ofertas (employer_id)
[x] Integrar fetch_company en pipeline (entre classify y evaluate)
[x] Añadir columna employer_id a offers en schema.sql
[x] Capturar author.id de API InfoJobs en fetch.py

## FASE 4 — Inteligencia
  [ ] role_discovery.py
  [ ] market_signals.py
  [ ] strategic_advisor.py con todos los triggers

## FASE 5 — Automatización
  [ ] Configuración cron
  [ ] Logging y monitorización

## TESTS
[x] tests/conftest.py con fixtures DB (temp file + rollback)
[x] Fixtures: sample_perfil_text, sample_offer (6 variants)
[x] Unit tests: test_evaluate.py, test_send.py, test_cleaner.py, test_fetch.py, test_models.py (107 tests)
[x] Integration tests: test_db_operations.py, test_db_evaluations.py (20 tests)
[x] Ollama cassettes (13 JSON en tests/fixtures/ollama/ + patch-based tests)
[x] Integration cassettes: test_evaluate_cassettes.py, test_classifier_cassettes.py, test_fetch_cassettes.py (30 tests cassette-based)
[x] Pipeline tests: test_pipeline.py (10 tests, flujo completo con cassettes)
[x] 167 tests passing total

## BUGS DETECTADOS POR TESTS
  [x] save_evaluation: añadidas 7 columnas faltantes al INSERT (cv_version_id, company_fit_score, etc.)
  [x] pre_filtro_requisitos_imposibles: PROFILE_CHECK_PATTERNS comparaba regex vs string
  [x] test_phase1.py: eliminada (tabla candidate_profile ya no existe)