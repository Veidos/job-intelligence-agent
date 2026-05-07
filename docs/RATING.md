# Sistema de Rating

El rating final combina dos evaluaciones independientes: técnica (qwen2.5) y HR (gemma4).

## Evaluación Técnica (qwen2.5 - 60 pts)

| Campo | Puntos | Descripción |
|-------|--------|-------------|
| `skills_hard_match` | 0-25 | Overlap entre skills requeridas en oferta vs skills del CV |
| `experience_match` | 0-15 | Años de experiencia requeridos vs años reales del candidato |
| `education_match` | 0-10 | Nivel educativo requerido vs nivel del candidato |
| `location_match` | 0-10 | Modalidad (remoto/híbrido/presencial) + ubicación |

**Reglas de location_match:**
- Remoto = 5 puntos
- Híbrido = 3 puntos
- Presencial en otra ciudad = 1 punto
- Presencial sin posibilidad de remoto = 0 puntos

**Regla crítica:** Si la oferta NO pide experiencia previa → experience_match = 18-20 puntos.

## Evaluación HR (gemma4 - 40 pts)

| Campo | Puntos | Descripción |
|-------|--------|-------------|
| `trajectory_coherence` | 0-15 | Coherencia del trayectoria profesional con el puesto |
| `recency_relevance` | 0-15 | Qué tan reciente es la experiencia relevante |
| `market_competitiveness` | 0-10 | Cómo compite este perfil en el mercado real |
| `penalty` | hasta -30 | Por gap laboral injustificado, incoherencia grave, requisitos no cumplidos |

**Penalty breakdown (ejemplos):**
- Gap laboral > 3 años sin justificar: -10
- Cambio de carrera sin experiencia relevante: -15
- Requisitos obligatorios no cumplidos: -5 a -20

**NO incluir en penalty:**
- Salario mínimo viable del candidato (nunca es factor de penalización)
- Factores de entorno (ritmo, presencialidad, cultura) — son contexto, no filtro

## Prompt de gemma4 para Evaluación HR

El evaluador HR debe ser honesto y profesional. No suavizar la realidad.

```
Eres un recruiter senior con criterio real. Tu evaluación debe ser
honesta y profesional. NO suavices la realidad. Evalúa como si tuvieras
que defender tu decisión ante un comité de selección.

Consideraciones especiales:
1. ¿El trayecto profesional tiene sentido para este puesto?
2. ¿El gap laboral es descalificante para esta oferta concreta?
3. ¿La empresa y su cultura presentan factores relevantes para este candidato?
4. ¿Qué haría un recruiter real con este CV en el primer filtro?
5. Dado el contexto personal declarado (personal_concerns), ¿es prudente invertir energía aquí?
6. Considerando la edad del candidato y que es un cambio de carrera:
   ¿La empresa típicamente contrata perfiles de reconversión en esta franja de edad?
```

## Rating Final

| Score | Label | Acción |
|-------|-------|--------|
| 75-100 | Prioritario | Alta prioridad para aplicar |
| 55-75 | Aplicar | Vale la pena aplicar |
| 35-54 | Con expectativas bajas | Aplicar solo si no hay mejores opciones |
| 0-34 | No aplicar | No recomendar |

## Selección Diaria (Top 3)

```python
def select_daily_top3(ofertas: list) -> list:
    """
    - score >= 35 mínimo
    - máximo 3 ofertas
    - score 35-54: incluir con nota "Incluida por falta de opciones superiores"
    - Si no hay >= 35: enviar "Sin ofertas relevantes hoy."
    """
```

## Coherencia HR/Técnico

Si gemma4 recomienda aplicar (`apply_signal: yes/maybe`) pero el score técnico es < 35, qwen2.5 hace una segunda evaluación para validar si realmente hay match.

Esto evita que ofertas con buenos argumentos de gemma4 pero poor Technical pasen el filtro.