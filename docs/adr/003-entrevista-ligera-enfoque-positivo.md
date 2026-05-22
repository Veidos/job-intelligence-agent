# 003 — Entrevista ligera con enfoque positivo

**Fecha:** 2026-05-22
**Tipo:** `operativo`
**Estado:** `activo`

## Contexto
La entrevista original tenía 6 preguntas efectivas, incluyendo una sobre
inseguridades laborales que generaba ansiedad innecesaria. El campo
`salary_min_viable` existía en PERFIL.md pero nunca se preguntaba.
Además, `work_mode_preference` y `relocation_conditions` eran preguntas
separadas cuando podían fusionarse en una sola respuesta abierta.

## Decisión
Rediseñar la entrevista a 5 preguntas, eliminando la pregunta negativa
y añadiendo salario opcional y motivación profesional:

1. **Modalidad + mudanza** (una sola pregunta abierta, procesada por gemma4)
2. **Salario mínimo viable** (nueva, opcional — vacío = no filtrar)
3. **Contexto personal** (todo en un solo input, con ejemplos de qué incluir)
4. **Motivación profesional** (enfoque positivo, sustituye inseguridades)
5. **Sectores preferidos / a evitar** (procesado por gemma4 a keywords)

Los ejemplos en cada pregunta son genéricos, no hardcodeados al perfil
del candidato.

## Alternativas descartadas
- **Mantener la pregunta de inseguridades:** contraproducente, genera
  autodiagnóstico negativo que contamina personal_concerns.
- **Pregunta 3 dividida en dos inputs (condiciones + entorno):** confuso,
  el usuario no sabe si debe repetir información o separarla.
- **Salario obligatorio:** rompe el flujo si no se quiere filtrar por salario.

## Consecuencias
- `work_mode_preference`, `location_preference` y `relocation_conditions`
  se extraen desde una sola respuesta mediante gemma4.
- `personal_concerns` es texto libre sin estructura forzada.
- La motivación se almacena como parte de `personal_concerns` para que
  gemma4 la use como contexto psicológico en evaluaciones.
- Los ejemplos deben mantenerse genéricos al modificar la entrevista.
