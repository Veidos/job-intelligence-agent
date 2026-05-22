# 002 — CV freshness check con regeneración interactiva

**Fecha:** 2026-05-21
**Tipo:** `operativo`
**Estado:** `activo`

## Contexto
El pipeline ejecutaba `evaluate()` contra `PERFIL.md` incluso cuando el CV
(`assets/cv.pdf`) estaba desactualizado, generando evaluaciones inconsistentes.
El usuario debía acordarse de lanzar `onboarding/run.py` manualmente tras cada
actualización del CV.

## Decisión
`run.py` detecta cambios en `assets/cv.pdf` vía SHA-256, pregunta al usuario
si quiere regenerar `PERFIL.md` con entrevista completa, y si acepta ejecuta
onboarding completo antes de continuar el pipeline. En `--dry-run` o ejecución
headless (cron), solo advierte y se detiene.

## Alternativas descartadas
- **Regeneración automática sin preguntar:** viola la regla de AGENTS.md
  (nunca auto-regenerar PERFIL.md sin confirmación explícita).
- **Solo warning sin opción interactiva:** mala UX para el usuario promedio
  que no quiere acordarse de comandos manuales.
- **Watcher continuo en background:** sobreingeniería para el caso de uso real.

## Consecuencias
- `.cv_hash` se crea en la raíz del proyecto (gitignored).
- El primer `run.py` post-CV ejecuta onboarding completo (extracción +
  entrevista), alargando el tiempo de ese run.
- Zero impacto en el flujo normal: CV sin cambios = 0 líneas adicionales.
- En headless (cron) el pipeline no se ejecuta si hay CV nuevo, evitando
  evaluaciones inconsistentes.
