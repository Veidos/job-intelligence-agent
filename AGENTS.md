# AGENTS.md — Job Intelligence Agent
> Proyecto: job-intelligence-agent  
> Candidato: Miguel Bohórquez Granados  
> Máquina: veidos@veidos-H310-Gaming-Trident3-MS-B920 (Ubuntu)  
> Stack: Python 3.14+, SQLite, Ollama, Telegram, cron  

---

## CONTEXTO DEL PROYECTO

Sistema de inteligencia de carrera que extrae ofertas de trabajo de InfoJobs,
las evalúa contra el perfil del candidato usando dos modelos locales de Ollama,
y envía un resumen diario por Telegram. El sistema aprende del mercado con el
tiempo y genera recomendaciones estratégicas cuando detecta patrones de rechazo
o mercado inactivo.

**Fuente única de verdad del candidato:** `PERFIL.md` en la raíz del proyecto.
Leer este archivo SIEMPRE antes de cualquier tarea de evaluación o análisis.

---

## SETUP Y EJECUCIÓN

```bash
# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python src/db/init_db.py

# Onboarding inicial (genera PERFIL.md)
python src/onboarding/run.py --cv assets/cv.pdf

# Ejecución manual del pipeline completo
python src/pipeline/run.py

# Ejecutar solo fetch de ofertas
python src/pipeline/fetch.py

# Ejecutar solo evaluación
python src/pipeline/evaluate.py

# Enviar Telegram manualmente
python src/telegram/send.py --mode daily

# Linter y formato (siempre antes de dar una tarea por terminada)
ruff check src/
ruff format src/
```

**Cron configurado** (no modificar sin avisar):
```
0 9 * * * /home/veidos/proyectos/job-intelligence-agent/.venv/bin/python /home/veidos/proyectos/job-intelligence-agent/src/pipeline/run.py
```

---

## ESTRUCTURA DEL PROYECTO

```
job-intelligence-agent/
├── AGENTS.md                  ← este archivo
├── PERFIL.md                  ← fuente de verdad del candidato (NO auto-generar)
├── PLANS.md                   ← estado del proyecto (Método Ledger)
├── MEMORIES.md                ← aprendizajes acumulados del sistema
├── requirements.txt
├── .env                       ← credenciales (NO commitear)
├── .gitignore
├── assets/
│   └── cv.pdf                 ← CV original del candidato
├── src/
│   ├── onboarding/
│   │   ├── run.py             ← orquesta el onboarding completo
│   │   ├── cv_extractor.py    ← qwen2.5 extrae datos del CV
│   │   └── interviewer.py     ← gemma4 conduce entrevista guiada
│   ├── pipeline/
│   │   ├── run.py             ← pipeline completo (fetch → eval → send)
│   │   ├── fetch.py           ← InfoJobs API → limpieza → DB
│   │   └── evaluate.py        ← qwen2.5 técnico + gemma4 HR
│   ├── intelligence/
│   │   ├── role_discovery.py  ← infiere roles accesibles del dataset
│   │   ├── market_signals.py  ← tendencias semanales del mercado
│   │   └── strategic_advisor.py ← triggers automáticos → consejos
│   ├── company/
│   │   └── fetch_company.py   ← datos y reseñas de empresa desde InfoJobs
│   ├── telegram/
│   │   └── send.py            ← envío de mensajes (daily/weekly/alert)
│   ├── db/
│   │   ├── init_db.py         ← crea esquema desde schema.sql
│   │   ├── schema.sql         ← definición completa del esquema
│   │   └── models.py          ← SQLAlchemy models
│   └── utils/
│       ├── ollama_client.py   ← wrapper para llamadas a Ollama
│       └── cleaner.py         ← limpieza y normalización de datos
├── data/
│   └── jobs.db                ← base de datos SQLite
├── logs/
│   └── pipeline.log
└── tests/
    └── test_phase1.py
```

---

## MODELOS OLLAMA Y SUS ROLES

El sistema usa **dos modelos con responsabilidades distintas**. No intercambiarlos.

| Modelo | Rol | Temperatura | Cuándo usarlo |
|--------|-----|-------------|---------------|
| `qwen2.5-coder:7b` | Motor técnico | 0.1 | Extracción de datos estructurados, análisis de skills, scoring cuantitativo, parsing de CV. Siempre responde en JSON. |
| `gemma4:e4b` | Evaluador HR + consejero | 0.4 | Razonamiento contextual, evaluación de empresa, lectura de `personal_concerns`, consejos estratégicos, texto narrativo. |

**Regla crítica:** qwen2.5 nunca produce texto narrativo libre. gemma4 nunca
produce scores numéricos sin razonamiento previo explícito.

**Nota sobre gemma4:e4b:** Es un modelo MoE (Mixture of Experts). Solo activa
una fracción de sus parámetros en cada inferencia, por lo que la memoria real
utilizada es aproximadamente la mitad del tamaño del modelo. Sus tareas son de
razonamiento, no de velocidad, por lo que la latencia mayor es aceptable.
Ejecutar siempre de forma secuencial respecto a qwen2.5, nunca en paralelo.

### Llamadas a Ollama

Usar siempre `src/utils/ollama_client.py`. No llamar a `requests` directamente.

```python
from src.utils.ollama_client import ollama_call

# Para qwen2.5 (siempre pedir JSON)
result = ollama_call(
    model="qwen2.5-coder:7b",
    prompt=prompt,
    expect_json=True
)

# Para gemma4 (texto libre o JSON según contexto)
result = ollama_call(
    model="gemma4:e4b",
    prompt=prompt,
    expect_json=False
)
```

---

## BASE DE DATOS

**Motor:** SQLite en `data/jobs.db`  
**ORM:** SQLAlchemy (usar siempre, no SQL crudo salvo en `init_db.py`)  
**Convención de nombres:** `snake_case` para todas las columnas.

### Tablas principales

```
offers              → ofertas crudas de InfoJobs
companies           → datos e inteligencia de empresa
offer_evaluations   → scoring técnico (qwen2.5) + HR (gemma4)
candidate_profile   → perfil estructurado (generado desde PERFIL.md)
cv_versions         → historial de versiones del CV
search_runs         → historial de ejecuciones del pipeline
market_signals      → señales semanales del mercado
strategic_insights  → consejos generados por el Strategic Advisor
```

### Reglas de base de datos

- Usar `upsert` por `source_id` en `offers` (nunca duplicar ofertas).
- `personal_concerns` en `candidate_profile` es TEXT libre — nunca normalizar
  ni intentar parsear su contenido.
- Los campos JSON se almacenan como TEXT serializado. Usar helpers en
  `src/db/models.py` para serializar/deserializar.
- No borrar registros históricos. Usar `is_active = False` para desactivar.

---

## SISTEMA DE RATING

El rating final combina dos evaluaciones independientes.

### Bloque A — qwen2.5 (60 puntos)

```
skills_hard_match    0–25  (overlap keywords skills requeridas vs CV)
experience_match     0–15  (años requeridos vs años reales)
education_match      0–10  (nivel/especialidad)
location_match       0–10  (modalidad + ubicación + condiciones de mudanza)
```

El `location_match` NO es una fórmula fija. Debe razonar con el contexto
completo del candidato: urgencia económica, condiciones de mudanza, si el
puesto cubre relocalización, compatibilidad con el perfil.

### Bloque B — gemma4 (40 puntos base, con penalizaciones hasta -30)

```
trajectory_coherence    0–15  (coherencia del trayecto profesional)
recency_relevance       0–15  (qué tan reciente es la experiencia relevante)
market_competitiveness  0–10  (cómo compite este perfil en el mercado real)
penalty                 0–30  (razonado desde personal_concerns)
```

### Prompt de gemma4 para evaluación HR

```
Eres un recruiter senior con criterio real. Tu evaluación debe ser
honesta y profesional. NO suavices la realidad. Evalúa como si tuvieras
que defender tu decisión ante un comité de selección.

PERFIL DEL CANDIDATO:
{contenido completo de PERFIL.md}

OFERTA A EVALUAR:
{datos de la oferta}

EMPRESA:
{datos de empresa si disponibles}

EVALÚA estos aspectos con rigor:
1. ¿El trayecto profesional tiene sentido para este puesto?
2. ¿El gap laboral es descalificante para esta oferta concreta?
3. ¿La empresa y su cultura presentan factores relevantes para este candidato?
   IMPORTANTE: Los factores de entorno (ritmo, presencialidad, cultura) NO son
   filtros de descarte. Son criterios de priorización cuando hay varias opciones
   y señales de preparación para entrevista cuando es la única opción viable.
   Para cada factor relevante detectado, indica qué preparación concreta
   necesitaría el candidato si llegara a entrevista.
4. ¿Qué haría un recruiter real con este CV en el primer filtro?
5. Dado el contexto personal declarado, ¿es prudente invertir energía aquí?

Responde en JSON con exactamente estos campos:
{
  "trajectory_coherence": int,
  "recency_relevance": int,
  "market_competitiveness": int,
  "penalty": int,
  "penalty_breakdown": {"motivo": puntos},
  "environment_compatibility": "alta|media|baja",
  "hr_concerns": ["string"],
  "strengths": ["string"],
  "red_flags": ["string"],
  "interview_prep": ["consejo concreto de preparación si hay factores a gestionar"],
  "verdict": "string (párrafo libre del recruiter)"
}
```

### Rating intrínseco de la oferta

```python
RATING = {
    range(75, 101): "Prioritario",
    range(55, 75):  "Aplicar",
    range(35, 55):  "Con expectativas bajas",
    range(0, 35):   "No aplicar",
}
```

### Lógica de selección diaria (top 3)

El rating intrínseco y la selección diaria son conceptos independientes.

```python
def select_daily_top3(ofertas: list) -> list:
    """
    Selecciona las mejores ofertas del día para enviar por Telegram.

    Prioridad: mayor score primero.
    Umbral mínimo de inclusión: score >= 35.
    Máximo: 3 ofertas.
    Si no hay ninguna >= 35: enviar aviso "Sin ofertas relevantes hoy."

    El rango 35-54 ("Con expectativas bajas") solo aparece en el mensaje
    si no hay suficientes ofertas de rango superior para completar el top 3.
    Las ofertas de este rango llevan nota explícita en el mensaje de Telegram.
    """
    candidatas = [o for o in ofertas if o.match_score >= 35]
    return sorted(candidatas, key=lambda o: o.match_score, reverse=True)[:3]
```

---

## PERFIL.md — REGLAS CRÍTICAS

- **Nunca regenerar `PERFIL.md` automáticamente** sin confirmación explícita
  del usuario. Este archivo puede contener información sensible editada
  manualmente.
- **Leer `PERFIL.md` al inicio de cada sesión** que implique evaluación,
  búsqueda o análisis estratégico.
- El campo `personal_concerns` es texto libre. No estructurar, no parsear,
  no resumir. Pasarlo íntegro a gemma4 como contexto.
- El campo `Entorno preferido / a evitar` NO es un filtro de descarte.
  Es información de priorización y preparación. Ver lógica de selección diaria.
- Si `PERFIL.md` no existe, ejecutar onboarding antes de cualquier otra tarea.
- Las secciones "Skills ausentes frecuentes" y "Headline sugerido" se
  actualizan automáticamente por `market_signals.py`. No editar manualmente.

---

## MÓDULOS DE INTELIGENCIA

### Role Discovery (`src/intelligence/role_discovery.py`)

Analiza el dataset acumulado de ofertas para inferir qué títulos de puesto
tienen overlap real con las skills del candidato, aunque no sean los roles
buscados explícitamente.

- Ejecutar cuando hay >50 ofertas acumuladas o al completar onboarding.
- Actualiza la sección "Roles descubiertos por el mercado" en `PERFIL.md`.
- Usa `qwen2.5` para clustering de skills, `gemma4` para interpretar los
  resultados y redactar la narrativa de cada rol sugerido.

### Market Signals (`src/intelligence/market_signals.py`)

Calcula señales semanales del mercado desde el dataset acumulado.
Escribe un registro en `market_signals` y actualiza `PERFIL.md`.

Señales clave: volumen de ofertas, competencia media (inscritos), skills
emergentes, tendencia salarial, % modalidad remota, temperatura del mercado.

### Strategic Advisor (`src/intelligence/strategic_advisor.py`)

Se activa por triggers automáticos. Evalúa condiciones y genera consejos.

```python
TRIGGERS = {
    "no_calls_3_weeks":    "aplicaciones > 5 AND llamadas = 0 AND semanas >= 3",
    "market_cold_2_weeks": "market_temperature = 'frio' AND semanas_frio >= 2",
    "skill_gap_detected":  "skill en >40% ofertas AND no esta en CV",
    "role_pivot_signal":   "match_score_promedio < 45 AND semanas >= 4",
}
```

Cuando se activa un trigger, gemma4 razona con datos reales del dataset.
El consejo se guarda en `strategic_insights` y se envía por Telegram.

---

## INFOJOBS API

**Autenticación:** HTTP Basic Auth con `CLIENT_ID` y `CLIENT_SECRET` desde
variables de entorno. No hardcodear credenciales nunca.

```bash
export INFOJOBS_CLIENT_ID="..."
export INFOJOBS_CLIENT_SECRET="..."
```

**Endpoints principales:**
- `GET /api/7/offer` — búsqueda de ofertas con filtros
- `GET /api/7/offer/{id}` — detalle completo de una oferta
- `GET /api/3/employer/{id}` — datos de empresa

**Queries de búsqueda iniciales** (expandibles con Role Discovery):
```python
SEARCH_QUERIES = [
    {"q": "data analyst", "province": ""},
    {"q": "analista de datos", "province": ""},
    {"q": "business intelligence", "province": ""},
    {"q": "cientifico de datos junior", "province": ""},
    {"q": "data analyst", "province": "41"},
    {"q": "data analyst", "province": "11"},
]
```

**Paginación:** máximo 20 resultados por página. Iterar hasta `totalResults`.
**Rate limiting:** respetar headers `X-RateLimit-Remaining`. Añadir `sleep(0.5)`
entre llamadas.

---

## TELEGRAM

**Bot token** desde variable de entorno:
```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

### Formato del mensaje diario (top 3 ofertas)

```
📋 OFERTAS DEL DÍA — {fecha}

🟢/🟡/🟠 {titulo} | {empresa}
📍 {modalidad} | {ciudad} | {salario_rango}
👥 {inscritos} inscritos | ⭐ {rating_empresa}/5
✅ Match: {match_score}/100 — {rating_label}
⚠️ {primer hr_concern si existe}
🎯 {primer interview_prep si existe}
🔗 {url_oferta}

— Si score 35-54: añadir nota "Incluida por falta de opciones superiores"
— Si no hay ofertas >= 35: enviar "Sin ofertas relevantes hoy."
```

### Formato del resumen semanal

Enviado los lunes. Incluye: temperatura del mercado, skills emergentes
detectadas, consejo del Strategic Advisor si hay trigger activo.

---

## ONBOARDING

El onboarding se ejecuta una sola vez (o cuando el usuario quiere actualizar
su perfil). Genera `PERFIL.md`.

### Fase 1 — Extracción del CV (qwen2.5)

Extraer sin preguntar: skills técnicas con nivel estimado, titulación,
experiencia (roles/sectores/fechas), idiomas, ubicación, gap laboral calculado
desde fechas, proyectos destacables, premios.

### Fase 2 — Entrevista guiada (gemma4)

Hacer UNA pregunta a la vez. Esperar respuesta antes de continuar.
Preguntar SOLO lo que el CV no puede decir:

1. Expectativa salarial mínima viable (no ideal — la mínima para decir sí)
2. Disponibilidad real de mudanza y condiciones
3. Preferencia de modalidad de trabajo
4. "¿Hay algo sobre tu situación actual que quieras que el sistema tenga en
   cuenta al evaluar las ofertas?" (campo personal_concerns — respuesta libre,
   no guiar, no sugerir categorías)
5. ¿Hay sectores o tipos de empresa que prefieras o quieras evitar?

### Fase 3 — Validación

Mostrar `PERFIL.md` generado. Pedir confirmación explícita antes de guardar.
Informar que puede editarlo manualmente en cualquier momento.

---

## CONVENCIONES DE CÓDIGO

- **Python 3.14+**. Type hints en todas las funciones públicas.
- **Linter:** `ruff check` y `ruff format` tras cada edición de código.
- **Imports:** absolutos desde `src/`. No imports relativos.
- **Logging:** usar `logging` estándar. No `print()` salvo en scripts de
  onboarding interactivos.
- **Variables de entorno:** todas en `.env` (no commitear). Cargar con
  `python-dotenv`.
- **Manejo de errores en llamadas a Ollama:** reintentar máximo 3 veces con
  backoff exponencial. Si falla, loguear y continuar con la siguiente oferta.
- **Manejo de errores en InfoJobs API:** loguear el error con contexto completo
  en `search_runs`. No abortar el pipeline por un error parcial.
- **JSON desde modelos:** validar siempre el schema antes de insertar en DB.
  Si el JSON es inválido, reintentar el prompt una vez con instrucción
  adicional de formato.
- **snake_case** para nombres de columnas y variables. **PascalCase** para
  clases. **UPPER_CASE** para constantes.

---

## MÉTODO LEDGER

Este proyecto usa el Método Ledger definido en `~/agente/prompts/system.md`.

- **`PLANS.md`** — mantener actualizado con el estado de cada módulo.
  Formato: fase actual, tareas completadas, tareas pendientes, blockers.
- **`MEMORIES.md`** — registrar aprendizajes no obvios: qué prompts funcionaron
  mejor, qué campos de InfoJobs son fiables, qué modelos rinden mejor
  en qué tareas.
- Actualizar ambos archivos al completar cada módulo o tarea significativa.

---

## FASES DE IMPLEMENTACIÓN

Implementar en este orden. No avanzar a la siguiente fase sin que la anterior
esté testeada y funcionando.

```
FASE 1 — Cimientos
  [x] init_db.py + schema.sql completo
  [x] ollama_client.py con reintentos y validación JSON
  [x] Test de conexión Telegram
  [x] Test de conexión Ollama
  [ ] Test de conexión InfoJobs API

FASE 2 — Onboarding
  [x] cv_extractor.py (qwen2.5 → datos estructurados)
  [x] interviewer.py (gemma4 → preguntas secuenciales)
  [x] Generación de PERFIL.md
  [ ] Guardado en candidate_profile (DB)

FASE 3 — Pipeline base
  [ ] fetch.py (InfoJobs API → limpieza → upsert en DB)
  [ ] fetch_company.py (datos empresa → DB)
  [ ] evaluate.py (qwen2.5 técnico + gemma4 HR → offer_evaluations)
  [ ] send.py (formato Telegram → envío)
  [ ] run.py (orquestador del pipeline completo)

FASE 4 — Inteligencia
  [ ] role_discovery.py
  [ ] market_signals.py
  [ ] strategic_advisor.py con todos los triggers

FASE 5 — Automatización
  [ ] Configuración cron
  [ ] Logging y monitorización
  [ ] Tests de integración end-to-end
```

---

## DATOS SENSIBLES

- `personal_concerns` y cualquier campo de contexto personal: no loguear,
  no imprimir en consola, no incluir en mensajes de error.
- Credenciales API siempre en variables de entorno, nunca en código o logs.
- `PERFIL.md` no se commitea a repositorios públicos. Añadir a `.gitignore`.
- `data/jobs.db` no se commitea. Añadir a `.gitignore`.

---

## ARCHIVOS QUE LEER AL INICIO DE CADA SESIÓN

1. `PERFIL.md` — contexto del candidato
2. `PLANS.md` — estado actual del proyecto
3. `MEMORIES.md` — aprendizajes previos relevantes

Si alguno no existe, crearlo antes de continuar.
