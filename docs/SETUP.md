# Setup y Ejecución

## Instalación

```bash
pip install -r requirements.txt
python src/db/init_db.py
```

## Comandos Principales

| Comando | Descripción |
|---------|-------------|
| `python src/onboarding/run.py --cv assets/cv.pdf` | Onboarding inicial (genera PERFIL.md) |
| `python src/pipeline/run.py` | Pipeline completo (fetch → classify → evaluate → send) |
| `python src/pipeline/fetch.py` | Solo fetch de ofertas desde InfoJobs |
| `python src/pipeline/evaluate.py` | Solo evaluación de ofertas |
| `python src/telegram/send.py --mode daily` | Enviar ofertas por Telegram |

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