# Pipeline de Ejecución

## Flujo Principal

```
run.py: fetch → classify → evaluate → send
```

## 1. Fetch (fetch.py)

Extrae ofertas de trabajo desde InfoJobs usando Apify.

**Proceso:**
1. Lee `search_config` de la base de datos (configuración geográfica y de roles)
2. Construye URLs de búsqueda con jerarquía geo/rol
3. Ejecuta actor Apify (`lRxJmbuhggr0LU3uj`) para scrapear ofertas
4. Qwen2.5 enriquece cada oferta extrayendo: description_clean, skills_required, experience_min, education_level, salary_min/max
5. Upsert en DB por `source_id` (nunca duplicar ofertas)

**Clave:** Usar siempre `src/utils/ollama_client.py` para llamadas a modelos. No usar `requests` directamente.

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

Evalúa cada oferta contra el perfil del candidato con dos modelos.

### Bloque A — gemma4:e4b (60 puntos, temperatura 0.1)

| Campo | Puntos | Descripción |
|-------|--------|-------------|
| skills_hard_match | 0-25 | Overlap entre skills requeridas y CV |
| experience_match | 0-15 | Años requeridos vs años reales |
| education_match | 0-10 | Nivel educativo requerido |
| location_match | 0-10 | Modalidad + ubicación |

### Bloque B — gemma4 (40 puntos)

| Campo | Puntos | Descripción |
|-------|--------|-------------|
| trajectory_coherence | 0-15 | Coherencia del trayectoria profesional |
| recency_relevance | 0-15 | Qué tan reciente es la experiencia relevante |
| market_competitiveness | 0-10 | Cómo compite este perfil en el mercado |
| penalty | hasta -30 | Gap laboral, incoherencia, requisitos no cumplidos |

**Coherencia HR/Técnico:** Funcionalidad eliminada tras unificar a gemma4:e4b.

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