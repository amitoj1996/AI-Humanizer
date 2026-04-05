#!/bin/bash
# Start both backend and frontend in parallel.
# Usage: ./scripts/start.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting AI Humanizer..."
echo ""

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "WARNING: Ollama is not running. Humanization won't work."
    echo "  Start it in another terminal:  ollama serve"
    echo ""
fi

# Start backend
echo "Starting backend on http://localhost:8000 ..."
cd "$ROOT/backend"
source venv/bin/activate 2>/dev/null || true
python run.py &
BACKEND_PID=$!

# Wait for backend to initialize models
sleep 2

# Start frontend
echo "Starting frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Both servers running. Open http://localhost:3000"
echo "Press Ctrl+C to stop both."

# Trap Ctrl+C to kill both
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
