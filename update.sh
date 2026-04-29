#!/bin/bash
# update.sh — hace git pull y reinicia el bot
# Uso: bash update.sh

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$BOT_DIR/bot.pid"

echo "🔄 Actualizando desde GitHub..."

# 1. Matar bot anterior
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    kill "$OLD_PID" 2>/dev/null && echo "⏹️  Bot detenido (PID $OLD_PID)"
    rm "$PID_FILE"
fi

# 2. Git pull
cd "$BOT_DIR"
git pull --rebase
if [ $? -ne 0 ]; then
    echo "❌ git pull falló, abortando"
    exit 1
fi

# 3. Instalar dependencias si cambiaron
pip install -r requirements.txt -q 2>/dev/null

# 4. Arrancar bot en background
nohup python3 bot.py > bot.log 2>&1 &
echo $! > "$PID_FILE"
echo "✅ Bot arrancado (PID $(cat $PID_FILE))"
echo "📋 Logs: tail -f $BOT_DIR/bot.log"
