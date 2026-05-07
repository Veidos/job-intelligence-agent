# AGENTS.md — Job Intelligence Agent

> Proyecto: job-intelligence-agent
> Candidato: Miguel Bohórquez Granados
> Stack: Python 3.14+, SQLite, Ollama, Telegram, cron

---

## CONTEXTO DEL PROYECTO

Sistema de inteligencia de carrera que extrae ofertas de trabajo de InfoJobs,
las evalúa contra el perfil del candidato usando dos modelos locales de Ollama,
y envía un resumen diario por Telegram.

**Fuente única de verdad del candidato:** `PERFIL.md` en la raíz.
**Leer SIEMPRE** antes de cualquier tarea de evaluación o análisis.

---

## ÍNDICE DE DOCUMENTACIÓN

| Archivo | Descripción |
|---------|-------------|
| `docs/SETUP.md` | Instalación, comandos, cron |
| `docs/PIPELINE.md` | Flujo completo fetch→classify→evaluate→send |
| `docs/DATABASE.md` | Tablas, reglas, schema SQL |
| `docs/RATING.md` | Sistema de puntuación técnico + HR |
| `docs/CONVENTIONS.md` | Estilo de código, fases de implementación |

---

## COMANDOS PRINCIPALES

```bash
# Onboarding (primera vez)
python src/onboarding/run.py --cv assets/cv.pdf

# Pipeline completo
python src/pipeline/run.py

# Pipeline individual
python src/pipeline/fetch.py      # Fetch ofertas
python src/pipeline/evaluate.py    # Evaluar ofertas
python src/telegram/send.py --mode daily  # Enviar Telegram

# Linter (siempre antes de terminar tarea)
ruff check src/ && ruff format src/
```

---

## MODELOS OLLAMA

| Modelo | Rol | Temperatura |
|--------|-----|-------------|
| `qwen2.5-coder:7b` | Motor técnico (JSON) | 0.1 |
| `gemma4:e4b` | Evaluador HR + contexto | 0.4 |

**Regla:** qwen2.5 nunca texto libre. gemma4 nunca scores numéricos sin razonamiento.

Ver `docs/CONVENTIONS.md` para detalles de uso.

---

## PERFIL.md — REGLAS CRÍTICAS

- **Nunca regenerar** `PERFIL.md` automáticamente sin confirmación explícita
- **Leer siempre** al inicio de cada sesión que implique evaluación/búsqueda
- `personal_concerns`: texto libre, no estructurar, pasar íntegro a gemma4
- `Entorno preferido / a evitar`: contexto de priorización, no filtro de descarte

---

## DATOS SENSIBLES

- `personal_concerns`: no loguear, no imprimir, no incluir en errores
- Credenciales: siempre en variables de entorno, nunca en código
- `PERFIL.md` y `data/jobs.db`: añadir a .gitignore (ya hecho)

---

## ARCHIVOS DE LECTURA OBLIGATORIA

Al inicio de cada sesión, leer en orden:

1. `AGENTS.md` — contexto técnico y reglas
2. `PLANS.md` — estado actual del proyecto
3. `MEMORIES.md` — aprendizajes acumulados
4. `PERFIL.md` — perfil del candidato
5. `src/db/schema.sql` — fuente de verdad de la DB

---

## CIERRE DE SESIÓN

Al finalizar cualquier sesión de trabajo:

```bash
git add -A
git commit -m "descripción breve"
git push
```

**Obligatorio.** No terminar sesión sin pushear.

---

## SISTEMA DE FEEDBACK (Telegram)

| Comando | Descripción |
|---------|-------------|
| `/f1 [texto]` | Feedback sobre oferta 1 |
| `/f2 [texto]` | Feedback sobre oferta 2 |
| `/f3 [texto]` | Feedback sobre oferta 3 |
| `/dia [texto]` | Estado emocional del día |

El feedback NO filtra ofertas. Es contexto psicológico para gemma4.

---

## AGENTES ESPECIALIZADOS

Disponible: `@pipeline` — agente especializado en el pipeline de ofertas.
Usa `.opencode/agents/pipeline.md` para contexto adicional.