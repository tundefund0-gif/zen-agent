#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f .env ]; then
    echo "Loading .env file..."
    set -a; source .env; set +a
fi

if [ -z "$OPENGATE_API_KEY" ]; then echo "OPENGATE_API_KEY not set"; exit 1; fi
if [ -z "$COMPOSIO_API_KEY" ]; then echo "COMPOSIO_API_KEY not set"; exit 1; fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt -q
fi

echo "Starting Zen Agent..."
echo "  Model:     ${OPENGATE_MODEL:-deepseek-v4-flash-free}"
echo "  Port:      ${PORT:-8000}"
echo "  Dashboard: http://localhost:${PORT:-8000}"

exec python3 -m uvicorn server.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8000}" \
    --log-level "${LOG_LEVEL:-info}" \
    --ws-ping-interval 30 \
    --ws-ping-timeout 10
