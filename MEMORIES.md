# MEMORIES.md — Aprendizajes del Sistema

## Configuración del proyecto
- Python 3.14+ requerido
- pypdf 6.10.2 instalado (usado para extracción de texto del CV)
- Ollama ejecutándose localmente en http://localhost:11434
- qwen2.5-coder:7b y gemma4:e4b confirmados disponibles

## Extracción de CV (cv_extractor.py)
- Limite de texto enviado a qwen2.5: 12000 caracteres (primeras páginas)
- qwen2.5 responde en JSON estructurado validado por ollama_client.py
- Campos extraídos: full_name, location_current, skills_technical, education, experience, languages, projects
- Si el modelo falla en devolver JSON, ollama_client reintenta con instrucción adicional

## Prompts efectivos
- qwen2.5-coder:7b: instrucción explícita "responde UNICAMENTE con JSON valido" + esquema de campos
- Temperatura baja (0.1) para extracción determinista

## Arquitectura de búsqueda y escalabilidad
- El sistema usa **source_adapter pattern** para escalabilidad multi-país.
  Ahora solo InfoJobs (España). Diseñado para añadir Indeed, LinkedIn etc
  sin reescribir fetch.py.
- La expansión geográfica y de rol es genérica: se infiere desde PERFIL.md
  vía qwen2.5, nunca hardcodeada.
