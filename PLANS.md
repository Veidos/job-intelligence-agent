# PLANS.md — Estado del Proyecto (Método Ledger)

> **Próximo paso:** Fase 2 (branding + microcopy dashboard) / Fase 4 (role_discovery, market_signals, strategic_advisor)
> T-8 ✅ — Feedback bot funcional y natural
> T-10 ✅ — Dashboard test checklist completado (ADR-015)
> **Sesión 2026-06-15:** Borrón y cuenta nueva, fixes scraper (403/dry-run/run_id/limit=0/published_at), pipeline completo 65 ofertas, 65 evaluadas, 3 "Aplicar" ✅
> **221 tests passing, pipeline funcional con scraper propio**

## FASE 1 — Cimientos
  [x] init_db.py + schema.sql completo
  [x] ollama_client.py con reintentos y validación JSON
  [x] Test de conexión Telegram
  [x] Test de conexión Ollama (gemma4:e4b)
  [x] Test de conexión InfoJobs API (vía Apify)

## FASE 2 — Onboarding
  [x] cv_extractor.py (gemma4 → datos estructurados)
  [x] interviewer.py (gemma4 → preguntas secuenciales)
  [x] Rediseño entrevista: preguntas positivas, salario opcional, contexto personal fusionado (ADR 003)
  [x] Generación de PERFIL.md (fuente única de verdad)
  [x] run.py orquesta el onboarding completo

## FASE 3 — Pipeline base
  [x] fetch.py (InfoJobs API → limpieza → upsert en DB)
  [x] evaluate.py (gemma4:e4b técnico + HR → offer_evaluations)
  [x] send.py (formato Telegram → envío)
  [x] run.py (orquestador del pipeline + CV freshness check vía SHA-256, ADR 002)
  [x] role_classifier.py (clasificación de ofertas y relevance_flag)
  [x] Añadir campos search_layer, role_level, relevance_flag a offers
  [x] Crear tabla search_config para configuración geográfica y de rol
  [x] Pre-filtro de requisitos impossibles (descartar 0/1)
  [x] fetch_company.py — enriquecimiento de companies desde ofertas (employer_id)
[x] Integrar fetch_company en pipeline (entre classify y evaluate)
[x] Añadir columna employer_id a offers en schema.sql
[x] Capturar author.id de API InfoJobs en fetch.py
  [x] apify_raw_responses — registro inmutable de raw data Apify
  [x] keyword_generator.py — generación y gestión de keywords desde PERFIL.md

## FASE 4 — Inteligencia
  [x] fetch_company.py — rediseñado con enriquecimiento LLM (qwen2.5:7b, sector, tamaño, descripción, flags)
  [x] Modelos hardcodeados eliminados — fetch.py, keyword_generator.py, role_classifier.py ahora usan MODEL_TECHNICAL
  [ ] role_discovery.py
  [ ] market_signals.py
  [ ] strategic_advisor.py con todos los triggers

## FASE 5 — Automatización
  [x] Listener de comandos Telegram (/f1, /f2, /f3, /dia) — handlers.py + bot.py
  [x] Persistencia de feedback con enlace a ofertas del día (get_latest_daily_offers corregido)
  [x] feedback_processor.py — procesa feedback acumulado a user_psychology
  [x] Scripts cron (setup_cron.sh, start_bot.sh, stop_bot.sh)
  [x] Logging persistente (RotatingFileHandler en run.py y bot.py)
  [x] Tests para feedback (test_feedback.py)
  [x] Tests para dashboard server REST API (test_dashboard_server.py, 18 tests)

## FASE 6 — Dashboard
  [x] Flask server.py con 6 secciones + Chart.js
  [x] Tabla applications (status, notes, contact_name, next_action_date)
  [x] API REST: stats, offers, companies, feedback, applications, runs
  [x] Modal detalle con scoring breakdown + inline feedback + application tracker
  [x] Timeline de aplicaciones agrupada por semana
  [x] Filtros por score, recomendación, señal, tipo, texto libre
  [x] Empresas clickeables → filtran ofertas
  [x] T-10 Dashboard test checklist en TESTING.md
  [x] T-5g — Rediseño profesional: 4 secciones jerárquicas (Ofertas, Aplicaciones, Empresas, Monitor), tabla 10 columnas (score, título, empresa, ubicación, modalidad, publicado, salario, recomendación, señal, bloqueo), modal con sticky CTA + descripción colapsable + enlace InfoJobs, apps con inline status, empresas charts, monitor narrativo, filterBlocked off por defecto, bugfixes skills/salary/fallback (ADR-015)

## TESTS
[x] tests/conftest.py con fixtures DB (temp file + rollback)
[x] Fixtures: sample_perfil_text, sample_offer (6 variants)
[x] Unit tests: test_evaluate.py, test_send.py, test_cleaner.py, test_fetch.py, test_models.py (107 tests)
[x] Integration tests: test_db_operations.py, test_db_evaluations.py (20 tests)
[x] Ollama cassettes (13 JSON en tests/fixtures/ollama/ + patch-based tests)
[x] Integration cassettes: test_evaluate_cassettes.py, test_classifier_cassettes.py, test_fetch_cassettes.py (30 tests cassette-based)
[x] Pipeline tests: test_pipeline.py (10 tests, flujo completo con cassettes)
[x] Scraper tests: test_scraper.py (39 tests: parser, published_at, skills dedup)
[x] 221 tests passing total (203 originales + 18 dashboard server API)

## BUGS DETECTADOS (TESTS Y REVISIÓN)
  [x] save_evaluation: añadidas 7 columnas faltantes al INSERT (cv_version_id, company_fit_score, etc.)
  [x] pre_filtro_requisitos_imposibles: PROFILE_CHECK_PATTERNS comparaba regex vs string
  [x] test_phase1.py: eliminada (tabla candidate_profile ya no existe)
  [x] Reportes HTML: `<title>` de v5 y v6 copiado de v4 sin actualizar ("T-4 v4" en la pestaña del navegador)
  [x] Reportes HTML: falta `ORDER BY id ASC` en queries SQL — IDs 241/242 invertidos en las cards
  [x] Navegación entre reportes: v3–v5 no tenían enlaces a versiones posteriores (imposible volver a v6 desde v5)
  [x] APIFY_TOKEN leído en module-level: movido a dentro de run_fetch()

## Testing pendiente — Pipeline completo

Ver checklist completo en docs/TESTING.md

- [x] T-0 — Prerequisitos verificados (4/5 🤖 OK, pendiente revisión 👤 ítem T-0.5)
- [x] T-1 — Onboarding validado manualmente (extracción + entrevista + PERFIL.md)
- [x] T-2 — fetch.py histórico completo (150 raw, 92 offers). Enriquecimiento con think=True + 8K ctx → 92/92 ✅
- [x] T-3 — fetch_company.py sin errores (68 empresas enriquecidas, 0 errores ✅)
- [x] T-4 — role_classifier.py coherente con las ofertas (92/92 clasificadas, 30 roles únicos, 0 contaminadas, ADR-005 documenta evolución)
- [x] T-5 — evaluate.py sin errores en tests
- [x] T-5b — evaluate.py real contra 92 ofertas (Batch 1 + 2 + 82 restantes), 0 errores
- [x] Dashboard de evaluaciones — `reports/evaluations-v2.html` (static HTML + Chart.js)
- [x] Scoring rebalance: F_exp sin gap, location_match determinista (ADR-013, código listo)
- [x] T-5c — Re-evaluar 92 ofertas con nueva fórmula (avg 41.4, 10 "Aplicar")
  - [x] Scoring rebalance + location_match determinista
  - [x] Zombie columns cleanup (7 columnas eliminadas)
- [x] T-5f — Flask dashboard con 6 secciones + API REST + applications + feedback inline
- [x] T-10 — Dashboard test checklist en TESTING.md
- [x] T-5g — Rediseño profesional dashboard: 4 secciones, tabla 10 columnas, modal sticky CTA, apps inline status, empresas charts, monitor narrativo (ADR-015)
- [x] T-5h — KPIs implementados (skills demand/gap, salary dist, weekly activity + sparkline, app funnel, model accuracy). server.py expone skill_detail + salary_min/max
- [x] T-6 — send.py — mensaje Telegram correcto
- [x] T-7 — run.py ciclo completo real sin errores (2026-06-06: 30 evaluadas, 25 nuevas, 0 errores) ✅
- [ ] T-8 — Feedback bot funcional y natural
- [x] T-9 — pytest 0 failed (221 tests, 0 regresiones)

## SESIÓN 2026-06-11 — Fixes de calidad
- [x] #1 — employer_id en RawOfferDetail + parser HTML scraper
- [x] #2 — employer_id en _upsert_offer_from_scraper() (INSERT/UPDATE)
- [x] #3 — --limit separado en --limit-eval (30) y --limit-enrich (50)
- [x] #4 — Global _run_start_time eliminada, t0 local
- [x] #5 — Log "[CV] Pipeline abortado" en no-TTY
- [x] #6 — skills_hard_match documentado (no renombrado, 25 referencias)
- [x] #7 — perfil[:2500]/[:2000] → profile.excerpt() (secciones por regex)
- [x] #8 — _extract_relevant_description() prioridad inversa en classifier
- [x] #9 — CandidateProfile en src/utils/candidate_profile.py (parseo unificado)
- [x] #10 — Warnings en GAP_TO_FLAG y relevance_corrected fallbacks
- [x] #12 — LLM quality metrics (calls, json_parse_failures, empty_responses)
- [x] #11 — location_match status quo (no ponderar en score) — cerrado
- [x] #13 — CandidateProfile compartido (resuelto por #9) — cerrado
- [x] ADR-018 — CandidateProfile, LLM Metrics, location_match Status Quo

## POST-FASE 7 — Optimización post-scraper (ADR-017)
- [x] Skills del `<dl>` "Conocimientos" van directamente a core (elimina reclasificación LLM)
- [x] `enrich_pending()` eliminado (Phase 3) — el scraper setea enriched_at en el upsert
- [x] `--enrich-only` eliminado del CLI
- [x] `role_level_label` eliminado del scoring — L binario (presencia, no profundidad)
- [x] `level_multiplier()`, `LEVEL_ORDINAL`, `ROLE_LEVEL_TO_SKILL_LEVEL` eliminados
- [x] ADR-017 documenta el cambio completo

## FASE 7 — Custom Scraper (ADR-016)
- [x] T-A1 — Implementar scraper propio (infojobs_scraper.py) con curl_cffi + BeautifulSoup
  - [x] Validar TLS fingerprint bypass con search y detail pages reales
  - [x] Guardar 3 snapshots HTML para tests
  - [x] Módulo search: GET a resultados, parsear lista de ofertas con filtro publicidad
  - [x] Módulo detail: GET a oferta individual, extraer Requisitos estructurados (estudios, experiencia, idiomas, conocimientos, sector)
  - [x] Header heurístico por texto (ciudad multi-word, modalidad, salario, contrato)
  - [x] InfoJobsScraper HTTP layer con paginación, rate limiting, reintentos
  - [x] 33 tests unitarios pasando contra snapshots reales
  - [x] Reemplazar Apify en fetch.py (con flag --use-apify como fallback)
  - [x] Validar contra ofertas reales (comparar campos vs Apify)
- [x] T-A2 — Migrar completamente a scraper propio, eliminar dependencia Apify
  - [x] `scraper_raw_responses` tabla append-only (UNIQUE offer_id)
  - [x] `persist_scraper_raw` + `upsert_from_scraper_raw` (3 fases como Apify)
  - [x] Eliminar ApifyClient import y run_fetch()
  - [x] Eliminar --use-apify del CLI
  - [x] Eliminar apify_client/apify_shared de requirements.txt
  - [x] apify_raw_responses preservada como legacy
  - [x] ADR-016 marcado completed
  - [x] 240 ofertas validadas: 100% exp_min, 75% edu, 100% skills
- [x] T-A3 — Post-production bugfixes (3 bugs)
  - [x] Skills duplicados: `list(dict.fromkeys(skills))` en `_parse_skills()`
  - [x] Descripciones vacías (21 ofertas): selectores semánticos + guard `len > 100`
  - [x] `published_at` nulo: `_extract_published_at()` parsea 5 formatos de texto plano
  - [x] Re-scrape de 21 ofertas con `scraper_lab/reparse_offers.py`
- [x] T-A4 — `--since-date` conectado al scraper (ya no es no-op, pasa `sinceDate` real)
- [x] T-A5 — Eliminar `build_search_urls()` (código muerto de era Apify)
- [x] T-A6 — Backfill `published_at` retroactivo con `scraper_lab/fix_published_at.py` (43/44 ofertas)