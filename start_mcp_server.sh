#!/bin/bash
# Mem0 MCP-Server Starter Script

echo "🚀 Starting mem0 MCP-Server..."
echo ""

# Aktiviere venv
source .venv/bin/activate

# Lade Environment-Variablen aus .env
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . .env
  set +a
else
  echo "⚠️  .env nicht gefunden, starte ohne zusätzliche Variablen"
fi

# Suppress HuggingFace progress bars (corrupt MCP SSE stream)
# export HF_HUB_DISABLE_PROGRESS_BARS=1
# export TRANSFORMERS_VERBOSITY=error
# Ollama handles GPU - no direct CUDA setup needed

# Wechsle ins API-Verzeichnis
cd openmemory/api

echo "✓ Virtual environment activated"
echo "✓ Environment variables set"
echo "✓ Working directory: $(pwd)"
echo ""
echo "Configuration:"
echo "  - LLM: Mistral (mistral-medium-latest)"
echo "  - Embeddings: BGE-M3 via Ollama (1024 dims)"
echo "  - Vector Store: Qdrant (http://your-qdrant-host:6333)"
echo ""
echo "Starting server on http://0.0.0.0:8765"
echo "API Docs: http://localhost:8765/docs"
echo "MCP Endpoint: http://localhost:8765/mcp/claude-desktop/sse/your-username"
echo ""
echo "Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Starte Server
uvicorn main:app --host 0.0.0.0 --port 8765
