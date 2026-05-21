# 001 — ADR como sistema de documentación de decisiones

**Fecha:** 2026-05-21
**Tipo:** `arquitectura`
**Estado:** `activo`

## Contexto
Las decisiones tomadas durante el desarrollo no quedaban registradas de forma
estructurada. MEMORIES.md acumulaba hechos técnicos pero no el razonamiento
detrás de cada decisión.

## Decisión
Usar ADR clásico: un fichero por decisión en docs/adr/, con formato fijo
y numeración secuencial.

## Alternativas descartadas
DECISIONS.md monolítico: peor para indexación por agentes, no escala,
git blame menos útil.

## Consecuencias
El agente crea un nuevo fichero ADR al final de cada sesión donde se tome
una decisión no trivial. El índice en docs/adr/README.md se actualiza siempre.
