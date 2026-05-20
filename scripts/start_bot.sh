#!/bin/bash
# Arrancar el bot de Telegram como daemon
# Uso: ./scripts/start_bot.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="/tmp/job_bot.pid"
LOG_FILE="$PROJECT_DIR/logs/bot.log"

mkdir -p "$PROJECT_DIR/logs"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "El bot ya está corriendo con PID $PID"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

cd "$PROJECT_DIR"
PYTHONPATH="$PROJECT_DIR" nohup python -m src.telegram.bot > "$LOG_FILE" 2>&1 &
BOT_PID=$!
echo $BOT_PID > "$PID_FILE"
echo "Bot iniciado con PID $BOT_PID"
echo "Logs en: $LOG_FILE"