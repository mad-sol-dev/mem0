#!/usr/bin/env python3
"""
mem0 Boot - Startet mem0 Server direkt, koppelt an Claude Desktop/Codex Lifecycle.

- Prüft ob Server bereits läuft (Port-Check)
- Erster Starter wird Owner, nur Owner stoppt den Server
- Mehrere Clients (Claude Desktop + Codex) können gleichzeitig nutzen
"""

import json
import subprocess
import sys
import signal
import socket
import os

VENV_PYTHON = "/home/martinm/programme/mem0/.venv/bin/python3"
WORKDIR = "/home/martinm/programme/mem0/openmemory/api"
PORT = 8765

proc = None
is_owner = False  # True wenn wir den Server gestartet haben

def log(msg):
    print(f"[mem0-boot] {msg}", file=sys.stderr, flush=True)

def port_in_use(port):
    """Prüft ob ein Port bereits belegt ist."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_server():
    global proc, is_owner

    if port_in_use(PORT):
        log(f"Server läuft bereits auf Port {PORT} - nutze existierenden")
        return

    log("Starte mem0 Server...")
    is_owner = True

    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "QX42UVrPAbU7RT1s7fdjnC7Jx3BllXRM"
    env["OPENAI_BASE_URL"] = "https://api.mistral.ai/v1"
    # Qdrant über VPN
    env["QDRANT_HOST"] = "10.8.0.1"
    env["QDRANT_PORT"] = "6333"
    # Suppress HuggingFace progress bars (corrupt MCP SSE stream)
    env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    env["TRANSFORMERS_VERBOSITY"] = "error"

    proc = subprocess.Popen(
        [VENV_PYTHON, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(PORT)],
        cwd=WORKDIR,
        env=env,
        stdout=sys.stderr,  # uvicorn output zu stderr
        stderr=sys.stderr
    )
    log(f"Server gestartet (PID {proc.pid})")

def stop_server():
    global proc, is_owner
    if proc and is_owner:
        log("Stoppe mem0 Server...")
        proc.terminate()
        try:
            proc.wait(timeout=30)
            log("Server sauber beendet")
        except subprocess.TimeoutExpired:
            proc.kill()
            log("Server gekillt (Timeout)")
        log("GPU RAM frei")
    elif not is_owner:
        log("Nicht Owner - Server bleibt laufen")

def shutdown(sig, frame):
    stop_server()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    start_server()

    # Minimaler MCP Server - nur am Leben bleiben
    for line in sys.stdin:
        try:
            msg = json.loads(line.strip())
            msg_id = msg.get("id")
            method = msg.get("method", "")

            if method == "initialize":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "serverInfo": {"name": "mem0-boot", "version": "1.0"}
                    }
                }), flush=True)

            elif method == "tools/list":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"tools": []}
                }), flush=True)

        except:
            pass

    stop_server()

if __name__ == "__main__":
    main()
