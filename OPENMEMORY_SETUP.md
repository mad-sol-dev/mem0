# OpenMemory MCP-Server Setup

Dokumentation für mein lokales mem0/OpenMemory Setup mit Claude Desktop.

**Erstellt:** Januar 2026

---

## Was ist das?

Ein persönlicher Memory-Layer für Claude. Speichert Fakten aus Gesprächen in einer Vektordatenbank und macht sie später wieder abrufbar.

**Architektur:**
```
Claude Desktop
    ├── mem0-boot (stdio) ──→ startet uvicorn als Subprocess
    │                              ↓
    │                         localhost:8765 ──→ Qdrant (10.8.0.1)
    │                              │
    │                              ├── Mistral (extrahiert Fakten)
    │                              └── BGE-M3 (Embeddings, GPU)
    │
    └── mem0 (SSE) ─────────→ localhost:8765/mcp/.../sse
```

**On-Demand GPU:**
- Claude Desktop startet → mem0-boot startet uvicorn → GPU belegt (~2.1 GB)
- Claude Desktop beendet → mem0-boot stoppt uvicorn → GPU frei

---

## Meine Konfiguration

| Komponente | Wert |
|------------|------|
| **LLM** | Mistral Medium (`mistral-medium-latest`) |
| **Embeddings** | BAAI/bge-m3 (1024 dims, GPU) |
| **Vector Store** | Qdrant `http://10.8.0.1:6333` (VPN) |
| **GPU** | NVIDIA RTX 3070, ~2.1 GB VRAM |
| **Python** | 3.11.2 in `.venv/` |

**Dateien:**
```
mem0/
├── openmemory/api/config.json   # Hauptkonfiguration
├── openmemory/api/.env          # API-Keys
├── mem0_boot.py                 # Boot-Script (startet uvicorn direkt als Subprocess)
├── start_mcp_server.sh          # Manueller Start (ohne Claude Desktop)
├── test_qdrant.py               # Test-Script
└── .venv/                       # Python Virtual Environment
```

---

## Claude Desktop Konfiguration

Datei: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mem0-boot": {
      "command": "/home/martinm/programme/mem0/.venv/bin/python3",
      "args": ["/home/martinm/programme/mem0/mem0_boot.py"]
    },
    "mem0": {
      "command": "npx",
      "args": ["@openmemory/install", "local", "http://localhost:8765/mcp/claude-desktop/sse/martinm"]
    }
  }
}
```

**Erklärung:**
- `mem0-boot` - Startet uvicorn direkt als Subprocess, stoppt beim Beenden von Claude Desktop
- `mem0` - Der eigentliche MCP-Server mit den Memory-Tools (verbindet zu localhost:8765)

Nach Änderung: Claude Desktop neu starten.

---

## Manueller Betrieb (ohne Claude Desktop)

Falls du mem0 ohne Claude Desktop nutzen willst:

```bash
cd /home/martinm/programme/mem0
./start_mcp_server.sh
```

Oder direkt mit uvicorn:
```bash
cd /home/martinm/programme/mem0
source .venv/bin/activate
source openmemory/api/.env
cd openmemory/api
uvicorn main:app --host 0.0.0.0 --port 8765
```

Server läuft dann auf `http://localhost:8765`.

---

## Web-UI (optional)

OpenMemory hat ein Web-Interface:

```bash
cd openmemory/ui
npm install   # einmalig
npm run dev   # startet auf http://localhost:3000
```

Benötigt laufenden API-Server auf Port 8765.

---

## Graceful Shutdown

mem0_boot.py sorgt dafür, dass laufende Schreiboperationen abgeschlossen werden:

- Bei SIGTERM/SIGINT wird uvicorn sauber beendet
- 30 Sekunden Timeout für laufende Requests
- Falls Timeout überschritten → SIGKILL
- Qdrant-Writes werden abgeschlossen bevor GPU freigegeben wird

---

## Testen

### Qdrant & Embeddings:
```bash
source .venv/bin/activate
source test_env.sh
python3 test_qdrant.py
```

### GPU prüfen:
```bash
source .venv/bin/activate
python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

### Qdrant erreichbar? (VPN muss aktiv sein)
```bash
curl http://10.8.0.1:6333
```

### Server läuft?
```bash
curl http://localhost:8765/docs
# Sollte HTML zurückgeben (200 OK)
```

---

## Wie es funktioniert

### Memory hinzufügen:
1. Claude sendet Konversation an OpenMemory
2. **Mistral Medium** extrahiert Fakten aus dem Text
3. **BGE-M3** (GPU) erstellt 1024-dimensionale Embeddings
4. Embeddings werden in **Qdrant** Collection `openmemory` gespeichert

### Memory suchen:
1. Suchanfrage wird mit BGE-M3 embedded
2. Qdrant findet ähnliche Vektoren (Cosine Similarity)
3. Relevante Memories werden zurückgegeben

---

## Qdrant Collections

Verschiedene Collections mit unterschiedlichen Dimensionen:

| Collection | Dimensionen | Nutzer |
|------------|-------------|--------|
| `open-webui_*` | 3072 | OpenWebUI |
| `technik`, `flowise` | 1024 | Andere Tools |
| `openmemory` | 1024 | mem0 (BGE-M3) |

Jede Collection ist isoliert - verschiedene Dimensionen sind kein Problem.

---

## Konfiguration ändern

### LLM wechseln:

In `openmemory/api/config.json`:
```json
"llm": {
    "config": {
        "model": "mistral-large-latest"
    }
}
```

Verfügbar: `mistral-small-latest`, `mistral-medium-latest`, `mistral-large-latest`

### Embedding-Modell wechseln:

```json
"embedder": {
    "config": {
        "model": "ANDERES-MODELL",
        "embedding_dims": NEUE-DIMENSION
    }
},
"vector_store": {
    "config": {
        "embedding_model_dims": NEUE-DIMENSION
    }
}
```

**Wichtig:** Bei Dimensions-Änderung muss die `openmemory` Collection in Qdrant gelöscht werden.

---

## Troubleshooting

### Server startet nicht
Logs von mem0-boot erscheinen in Claude Desktop's stderr. Alternativ manuell starten:
```bash
cd /home/martinm/programme/mem0/openmemory/api
source ../../.venv/bin/activate
source .env
uvicorn main:app --host 0.0.0.0 --port 8765
```

### GPU nicht erkannt
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Qdrant nicht erreichbar
- VPN aktiv? `ping 10.8.0.1`
- Port offen? `curl http://10.8.0.1:6333`

### "Invalid model" Fehler
Modellname in `config.json` prüfen.

---

## Neuinstallation

```bash
cd /home/martinm/programme/mem0
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[llms,vector_stores,extras]"
pip install torch --index-url https://download.pytorch.org/whl/cu118
pip install sentence-transformers fastapi uvicorn[standard] "mcp[cli]" fastapi-pagination sse-starlette
```

---

## Ressourcen

- mem0 Docs: https://docs.mem0.ai
- Qdrant: https://qdrant.tech/documentation/
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- Mistral API: https://docs.mistral.ai/
