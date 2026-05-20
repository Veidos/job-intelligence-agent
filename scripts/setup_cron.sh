#!/bin/bash
# Configuración de cron para el Job Intelligence Agent
# Uso: ./scripts/setup_cron.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Configurando cron para Job Intelligence Agent ==="
echo "Proyecto: $PROJECT_DIR"

# Crear directorio de logs si no existe
mkdir -p "$PROJECT_DIR/logs"

# Obtener usuario actual
USER=$(whoami)

# Eliminar entradas anteriores del cron (solo las nuestras)
crontab -l 2>/dev/null | grep -v "job-intelligence-agent" > /tmp/current_cron.tmp

# Añadir nuevas entradas
cat >> /tmp/current_cron.tmp << 'EOF'
# Job Intelligence Agent - Pipeline diario (L-V 08:00)
0 8 * * 1-5 cd /home/veidos/proyectos/job-intelligence-agent && PYTHONPATH=/home/veidos/proyectos/job-intelligence-agent python -m src.pipeline.run >> logs/pipeline.log 2>&1

# Job Intelligence Agent - Feedback processor (diario 21:00)
0 21 * * * cd /home/veidos/proyectos/job-intelligence-agent && PYTHONPATH=/home/veidos/proyectos/job-intelligence-agent python -m src.pipeline.feedback_processor >> logs/feedback.log 2>&1
EOF

# Instalar nuevo crontab
crontab /tmp/current_cron.tmp
rm /tmp/current_cron.tmp

echo "=== Cron instalado ==="
echo "Entradas activas:"
crontab -l | grep "job-intelligence-agent" || echo "(ninguna)"
echo ""
echo "Para verificar: crontab -l"
echo "Para editar: crontab -e"