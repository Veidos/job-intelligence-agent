#!/bin/bash
# Parar el bot de Telegram
# Uso: ./scripts/stop_bot.sh

PID_FILE="/tmp/job_bot.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "No hay PID guardado. ¿El bot está corriendo?"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    kill "$PID"
    sleep 1
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID"
    fi
    echo "Bot parado (PID $PID)"
else
    echo "El proceso $PID no está corriendo"
fi

rm -f "$PID_FILE"