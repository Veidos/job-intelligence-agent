# Pipeline de Ejecución

## Flujo Principal

```
run.py: fetch → classify → evaluate → send
```

## 1. Fetch (fetch.py)

Extrae ofertas de InfoJobs vía Apify. Opera en **dos fases separadas**.

### Fase 1 — `upsert_raw` (sin LLM)

1. Lee `search_config` de la base de datos
2. Construye searchUrls con jerarquía geo/rol
3. Ejecuta actor Apify (`lRxJmbuhggr0LU3uj`)
4. Persiste cada item con campos estructurales de Apify
   (`title`, `city`, `companyName`, `link`, `contractType`, `teleworking`,
   `description`, `salary`, etc.) + `raw_data` (JSON completo del item)
5. **No llama a ningún LLM** en esta fase

### Fase 2 — `enrich_pending` (con LLM)

1. Selecciona ofertas con `raw_data IS NOT NULL AND enriched_at IS NULL`
2. Para cada una: deserializa `raw_data`, llama a `extract_fields_with_llm`
   (gemma4:e4b, temperatura 0.0) para extraer:
   - `description_clean` — texto plano sin HTML
   - `role_level` — junior / mid / senior
   - `skills_required` — core y secondary (solo `name`, sin nivel)
   - `experience_min`, `education_level`
   - `salary_min`, `salary_max`
3. Actualiza la oferta y marca `enriched_at = NOW()`

**Si el LLM falla:** la oferta queda con `enriched_at IS NULL` y se reintenta
automáticamente en la próxima ejecución. La oferta raw nunca se pierde.

**Salida:** `raw_data` completo, `description_raw`, y campos estructurales
disponibles desde Fase 1 — incluso si el LLM nunca llega a funcionar.

## 2. Classify (role_classifier.py)

Clasifica cada oferta según el catálogo de roles.

**Proceso:**
1. Gemma4 analiza título + descripción de cada oferta
2. Asigna `role_normalized` desde el catálogo de roles
3. Asigna `relevance_flag`:
   - `core`: requisitos coinciden >70% con el perfil
   - `adjacent`: coinciden 40-70%
   - `stretch`: coinciden 20-40%
   - `temporal`: trabajo puente viable
4. Actualiza el catálogo si detecta nuevos roles

## 3. Evaluate (evaluate.py)

Evalúa cada oferta contra el perfil del candidato. **Cálculo determinista
con un solo prompt de contexto.**

### Componentes del score

| Componente | Peso | Origen | Método |
|-----------|------|--------|--------|
| `M_core` (skills core) | 0.45 | Python | Level multiplier por skill |
| `M_sec` (skills secundarias) | 0.15 | Python | Level multiplier por skill |
| `F_exp` (experiencia) | 0.25 | Python | years_match · gap_multiplier |
| `F_fit` (contexto) | 0.15 | gemma4:e4b | Evaluación cualitativa |

### Reglas clave

- **`level_required` no se persiste por skill.** Se resuelve en tiempo de
  evaluación desde `role_level_label` de la oferta mediante el mapping
  `ROLE_LEVEL_TO_SKILL_LEVEL`.
- **`gap_severity` se calcula en Python** (determinista), no se pide al LLM.
- **Sobrecualificación no penaliza** — el level multiplier capa a 1.0.
- **Validación final** (tercer prompt): detecta bloqueos reales
  (convenio prácticas, certificado discapacidad obligatorio) y valida
  `relevance_flag`.

Ver scoring completo en [`docs/RATING.md`](docs/RATING.md).

## 4. Send (send.py)

Envía el resumen diario por Telegram.

**Lógica de selección:**
- Score mínimo: 35
- Máximo: 3 ofertas
- Prioridad: mayor score primero
- Rango 35-54: añadir nota "Incluida por falta de opciones superiores"

**Feedback:**
- `/f1 [texto]` → feedback sobre oferta 1
- `/f2 [texto]` → feedback sobre oferta 2
- `/f3 [texto]` → feedback sobre oferta 3
- `/dia [texto]` → contexto emocional del día

## Módulos de Inteligencia (Pendientes)

Estos módulos analizan patrones para generar recomendaciones estratégicas:

| Módulo | Función |
|--------|---------|
| `role_discovery.py` | Infiere roles accesibles desde el dataset de ofertas |
| `market_signals.py` | Calcula señales semanales del mercado |
| `strategic_advisor.py` | Detecta triggers y genera consejos estratégicos |

**Triggers del Strategic Advisor:**
- `no_calls_3_weeks`: aplicaciones > 5, llamadas = 0, semanas >= 3
- `market_cold_2_weeks`: market_temperature = 'frio' >= 2 semanas
- `skill_gap_detected`: skill en >40% ofertas y no está en CV
- `role_pivot_signal`: match_score_promedio < 45 >= 4 semanas