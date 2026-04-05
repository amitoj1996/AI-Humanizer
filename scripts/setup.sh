#!/bin/bash
set -e

echo "========================================="
echo "  AI Humanizer & Detector — Setup"
echo "========================================="

# ---- Python backend ----
echo ""
echo "[1/4] Setting up Python backend..."
cd "$(dirname "$0")/../backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Created virtual environment."
fi

source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Python dependencies installed."

# Pre-download NLTK data
python3 -c "
import nltk
for pkg in ['wordnet', 'punkt_tab', 'averaged_perceptron_tagger']:
    nltk.download(pkg, quiet=True)
print('  NLTK data downloaded.')
"

# ---- Node frontend ----
echo ""
echo "[2/4] Setting up Next.js frontend..."
cd "$(dirname "$0")/../frontend"
npm install --silent
echo "  Frontend dependencies installed."

# ---- Ollama check ----
echo ""
echo "[3/4] Checking Ollama..."
if command -v ollama &> /dev/null; then
    echo "  Ollama found: $(which ollama)"
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "  Ollama is running."
        MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; [print('    -', m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null)
        if [ -n "$MODELS" ]; then
            echo "  Available models:"
            echo "$MODELS"
        else
            echo "  No models pulled yet. Run: ollama pull mistral"
        fi
    else
        echo "  Ollama installed but not running. Start with: ollama serve"
    fi
else
    echo "  Ollama not found. Install from: https://ollama.com"
    echo "  Then run: ollama pull mistral"
fi

# ---- Summary ----
echo ""
echo "[4/4] Setup complete!"
echo ""
echo "========================================="
echo "  To start the app:"
echo "  1. Start Ollama:    ollama serve"
echo "  2. Pull a model:    ollama pull mistral"
echo "  3. Start backend:   cd backend && source venv/bin/activate && python run.py"
echo "  4. Start frontend:  cd frontend && npm run dev"
echo "  5. Open:            http://localhost:3000"
echo "========================================="
