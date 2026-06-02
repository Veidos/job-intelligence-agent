# Setup y Ejecución

## Instalación

```bash
pip install -r requirements.txt
pip install flask
python src/db/init_db.py
```

## Comandos Principales

| Comando | Descripción |
|---------|-------------|
| `python src/onboarding/run.py --cv assets/cv.pdf` | Onboarding inicial (genera PERFIL.md) |
| `python src/onboarding/keyword_generator` | Generar keywords de búsqueda desde PERFIL.md |
| `python src/onboarding/keyword_generator --dry-run` | Vista previa de keywords sin guardar |
| `python src/onboarding/keyword_generator --manage` | Gestionar keywords (conservar/añadir) |
| `python src/dashboard/server.py` | **Dashboard web en http://localhost:8080** |
| `python src/dashboard/server.py --port 9090` | Dashboard en puerto personalizado |
| `python src/pipeline/run.py` | Pipeline completo (fetch → classify → evaluate → send) |
| `python src/pipeline/fetch.py` | Solo fetch de ofertas desde InfoJobs |
| `python src/pipeline/evaluate.py` | Solo evaluación de ofertas (default 10) |
| `python src/pipeline/evaluate.py --limit 0` | Evaluar todas las ofertas pendientes |
| `python src/pipeline/generate_dashboard.py` | Generar HTML legacy en reports/ (obsoleto, usar Flask) |
| `python src/telegram/send.py --mode daily` | (Opcional) Enviar ofertas por Telegram |

## Flujo post-onboarding

1. Ejecutar `python src/onboarding/keyword_generator` para generar los títulos de búsqueda
2. Verificar con `--dry-run`, ajustar con `--manage` si es necesario
3. Ejecutar `python src/pipeline/run.py` para el pipeline completo
4. Ejecutar `python src/dashboard/server.py` y abrir `http://localhost:8080` para ver resultados

## Linter y Formato

```bash
ruff check src/
ruff format src/
```

Ejecutar siempre antes de dar una tarea por terminada.

## Cron

El pipeline se ejecuta automáticamente cada día a las 9:00:

```
0 9 * * * /home/veidos/proyectos/job-intelligence-agent/.venv/bin/python /home/veidos/proyectos/job-intelligence-agent/src/pipeline/run.py
```

**No modificar sin avisar.**
