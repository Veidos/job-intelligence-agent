# Sistema de Rating — ADR-008

Score determinista 0–1. Ningún LLM genera puntuaciones numéricas.

## Fórmula

$$
S = W_{\text{core}} \cdot M_{\text{core}} + W_{\text{sec}} \cdot M_{\text{sec}} + W_{\text{exp}} \cdot F_{\text{exp}} + W_{\text{fit}} \cdot F_{\text{fit}}
$$

| Peso | Variable | Depende de |
|------|----------|-----------|
| 0.45 | `M_core` | Skills core de la oferta vs CV |
| 0.15 | `M_sec` | Skills secundarias de la oferta vs CV |
| 0.25 | `F_exp` | Años de experiencia + gap laboral |
| 0.15 | `F_fit` | gemma4:e4b (única intervención LLM) |

## Skills: nivel por skill

Cada skill tiene un nivel requerido inferido:

$$
\text{level\_required} = \begin{cases}
\text{sk\_level\_required} & \text{si la skill tiene level\_required explícito} \\
\text{ROLE\_LEVEL\_TO\_SKILL\_LEVEL[role\_level\_label]} & \text{si no tiene}
\end{cases}
$$

Mapping:

| `role_level_label` | Nivel inferido |
|---|---|
| junior | básico (ord=1) |
| mid | intermedio (ord=2) |
| senior | avanzado (ord=3) |

Multiplicador individual:

$$
L_i = \frac{\min(\text{ord}(lvl_{\text{cand}}), \text{ord}(lvl_{\text{req}}))}{\text{ord}(lvl_{\text{req}})}
$$

- Si el candidato no tiene la skill: `L_i = 0`
- Sobrecualificación: cap a 1.0
- `M_core = avg(L_i)` para skills core
- `M_sec = avg(L_i)` para skills secundarias

## Experiencia

$$
F_{\text{exp}} = \text{years\_match} \cdot G(\text{gap})
$$

$$
\text{years\_match} = \begin{cases}
1.0 & \text{si } experience\_min = 0 \\
\min(\frac{candidate\_years}{experience\_min}, 1.0) & \text{en otro caso}
\end{cases}
$$

### Gap multiplier

| Gap (años) | G |
|------------|---|
| 0 – <1 | 1.00 |
| 1 – <2 | 0.85 |
| 2 – <3 | 0.70 |
| 3 – <4 | 0.55 |
| ≥ 4 | 0.40 |

## Contexto

`F_fit` = único valor del LLM. gemma4:e4b evalúa `context_fit` (0–1)
considerando cultura, ubicación, modalidad y perfil personal.

## Rating final

| Score | Label |
|-------|-------|
| 0.75 ≤ S ≤ 1.00 | Prioritario |
| 0.55 ≤ S < 0.75 | Aplicar |
| 0.35 ≤ S < 0.55 | Con expectativas bajas |
| 0.00 ≤ S < 0.35 | No aplicar |

## Notas

- La temperatura HR = 0.0 garantiza veredictos deterministas
- Los skills `level_required` individuales (legacy) siguen siendo válidos
  si existen en DB; si son `None`, se resuelven automáticamente desde
  el rol de la oferta
- ADR-008 documenta la justificación completa del cambio a scoring
  determinista 0-1
