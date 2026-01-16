#!/usr/bin/env python3
"""
mem0 SSE Bridge - Saubere stdio-zu-SSE Bridge ohne npx-Garbage.

Verbindet Claude Desktop (stdio) mit dem mem0 MCP-Server (SSE).
"""

import asyncio
import json
import sys
import aiohttp
import concurrent.futures

SSE_URL = "http://localhost:8765/mcp/claude-desktop/sse/martinm"

def log(msg):
    print(f"[mem0-bridge] {msg}", file=sys.stderr, flush=True)

async def main():
    log("Starting SSE bridge...")

    messages_url = None
    session = aiohttp.ClientSession()

    # Stdin reader in thread
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()

    def read_stdin_line():
        try:
            return sys.stdin.readline()
        except:
            return None

    try:
        async with session.get(SSE_URL) as sse_response:
            # Parse SSE events
            buffer = ""

            async for chunk in sse_response.content.iter_any():
                chunk_str = chunk.decode('utf-8')
                buffer += chunk_str

                # Process complete events
                while '\r\n\r\n' in buffer:
                    event_block, buffer = buffer.split('\r\n\r\n', 1)

                    event_type = None
                    data = None

                    for line in event_block.split('\r\n'):
                        if line.startswith('event:'):
                            event_type = line[6:].strip()
                        elif line.startswith('data:'):
                            data = line[5:].strip()

                    if event_type == 'endpoint' and data:
                        messages_url = f"http://localhost:8765{data}"
                        log(f"Connected: {messages_url}")

                        # Starte stdin-Leser als background task
                        asyncio.create_task(stdin_reader(session, messages_url, executor, loop))

                    elif event_type == 'message' and data:
                        # JSON-RPC Response an stdout
                        print(data, flush=True)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        log(f"Error: {e}")
    finally:
        await session.close()
        executor.shutdown(wait=False)
        log("Bridge closed")

async def stdin_reader(session, messages_url, executor, loop):
    """Lese stdin und sende an Server."""
    def read_line():
        try:
            return sys.stdin.readline()
        except:
            return None

    while True:
        line = await loop.run_in_executor(executor, read_line)
        if not line:
            break

        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
            async with session.post(messages_url, json=msg) as resp:
                pass  # Response kommt via SSE
        except json.JSONDecodeError as e:
            log(f"Invalid JSON: {e}")
        except Exception as e:
            log(f"Send error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
