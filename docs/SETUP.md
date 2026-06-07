# Setup y Ejecución

## Instalación

```bash
pip install -r requirements.txt
python src/db/init_db.py
```

## Acceso Remoto (Tailscale)

Para ver el dashboard desde el móvil fuera de casa:

```bash
# 1. Instalar Tailscale en el PC
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 2. Anotar la IP de Tailscale
tailscale ip -4

# 3. Instalar Tailscale en el móvil (App Store / Google Play)
#    Autenticar con la misma cuenta

# 4. Arrancar dashboard accesible desde Tailscale
python src/dashboard/server.py --host 0.0.0.0 --port 8080

# 5. (Opcional) Servicio permanente
sudo cp scripts/job-dashboard.service /etc/systemd/system/
sudo systemctl enable job-dashboard
sudo systemctl start job-dashboard

# Acceder desde el móvil: http://<tailscale-ip>:8080
```

Tailscale cifra el tráfico con WireGuard E2E. Solo tus dispositivos autenticados pueden alcanzar el dashboard.

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
| `python src/pipeline/fetch.py` | Solo fetch de ofertas (default últimas 24h) |
| `python src/pipeline/fetch.py --since-date ANY` | Fetch sin filtro de fecha |
| `python src/pipeline/run.py --since-date ANY` | Pipeline sin filtro de fecha |
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
0 9 * * * /home/veidos/proyectos/job-intelligence-agent/.venv/bin/python /home/veidos/proyectos/job-intelligence-agent/src/pipeline/run.py --skip-cv-check
```

`--skip-cv-check` necesario porque cron no tiene TTY. Sin él, si el CV cambia el pipeline se detiene automáticamente.

**No modificar sin avisar.**
