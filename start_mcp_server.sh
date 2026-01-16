#!/bin/bash
# Mem0 MCP-Server Starter Script

echo "🚀 Starting mem0 MCP-Server..."
echo ""

# Aktiviere venv
source .venv/bin/activate

# Setze Environment-Variablen
export OPENAI_API_KEY="QX42UVrPAbU7RT1s7fdjnC7Jx3BllXRM"
export OPENAI_BASE_URL="https://api.mistral.ai/v1"

# Qdrant über VPN
export QDRANT_HOST="10.8.0.1"
export QDRANT_PORT="6333"

# Suppress HuggingFace progress bars (corrupt MCP SSE stream)
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TRANSFORMERS_VERBOSITY=error

# Wechsle ins API-Verzeichnis
cd openmemory/api

echo "✓ Virtual environment activated"
echo "✓ Environment variables set"
echo "✓ Working directory: $(pwd)"
echo ""
echo "Configuration:"
echo "  - LLM: Mistral (mistral-medium-latest)"
echo "  - Embeddings: BGE-M3 (1024 dims, GPU)"
echo "  - Vector Store: Qdrant (http://10.8.0.1:6333)"
echo ""
echo "Starting server on http://0.0.0.0:8765"
echo "API Docs: http://localhost:8765/docs"
echo "MCP Endpoint: http://localhost:8765/mcp/claude-desktop/sse/martinm"
echo ""
echo "Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Starte Server
uvicorn main:app --host 0.0.0.0 --port 8765
