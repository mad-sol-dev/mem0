#!/usr/bin/env python3
"""
mem0 SSE Bridge - Saubere stdio-zu-SSE Bridge ohne npx-Garbage.

Verbindet Claude Desktop (stdio) mit dem mem0 MCP-Server (SSE).
Features:
- Automatische Reconnection mit exponential backoff
- Robustes SSE-Parsing (handles \r\n und \n)
- Besseres Error-Logging
"""

import asyncio
import json
import sys
import traceback
import aiohttp
import concurrent.futures

SSE_URL = "http://localhost:8765/mcp/claude-desktop/sse/martinm"
MAX_RECONNECT_ATTEMPTS = 10
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 30  # seconds

def log(msg):
    print(f"[mem0-bridge] {msg}", file=sys.stderr, flush=True)

class SSEBridge:
    def __init__(self):
        self.session = None
        self.messages_url = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.loop = None
        self.stdin_task = None
        self.running = True
        self.reconnect_count = 0

    async def connect_sse(self):
        """Connect to SSE endpoint with reconnection logic."""
        backoff = INITIAL_BACKOFF

        while self.running and self.reconnect_count < MAX_RECONNECT_ATTEMPTS:
            try:
                if self.session is None or self.session.closed:
                    self.session = aiohttp.ClientSession()

                log(f"Connecting to SSE... (attempt {self.reconnect_count + 1})")

                async with self.session.get(SSE_URL, timeout=aiohttp.ClientTimeout(total=None)) as sse_response:
                    if sse_response.status != 200:
                        log(f"SSE connection failed: HTTP {sse_response.status}")
                        raise aiohttp.ClientError(f"HTTP {sse_response.status}")

                    # Reset backoff on successful connection
                    backoff = INITIAL_BACKOFF
                    self.reconnect_count = 0

                    await self.process_sse_stream(sse_response)

            except asyncio.CancelledError:
                log("SSE connection cancelled")
                break
            except aiohttp.ClientError as e:
                log(f"SSE client error: {e}")
            except Exception as e:
                log(f"SSE error: {type(e).__name__}: {e}")
                log(f"Traceback: {traceback.format_exc()}")

            if self.running:
                self.reconnect_count += 1
                log(f"Reconnecting in {backoff}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)

        if self.reconnect_count >= MAX_RECONNECT_ATTEMPTS:
            log(f"Max reconnect attempts ({MAX_RECONNECT_ATTEMPTS}) reached, giving up")

    async def process_sse_stream(self, response):
        """Process SSE stream with robust parsing."""
        buffer = ""

        async for chunk in response.content.iter_any():
            if not self.running:
                break

            chunk_str = chunk.decode('utf-8')
            buffer += chunk_str

            # Handle both \r\n\r\n and \n\n as event separators
            # Normalize to \n\n for easier parsing
            buffer = buffer.replace('\r\n', '\n')

            # Process complete events
            while '\n\n' in buffer:
                event_block, buffer = buffer.split('\n\n', 1)

                if not event_block.strip():
                    continue

                event_type = None
                data_lines = []

                for line in event_block.split('\n'):
                    line = line.strip()
                    if not line or line.startswith(':'):
                        # Comment or empty line, ignore
                        continue
                    if line.startswith('event:'):
                        event_type = line[6:].strip()
                    elif line.startswith('data:'):
                        data_lines.append(line[5:].strip())

                # Join multi-line data
                data = '\n'.join(data_lines) if data_lines else None

                if event_type == 'endpoint' and data:
                    self.messages_url = f"http://localhost:8765{data}"
                    log(f"Connected: {self.messages_url}")

                    # Start stdin reader if not already running
                    if self.stdin_task is None or self.stdin_task.done():
                        self.stdin_task = asyncio.create_task(self.stdin_reader())

                elif event_type == 'message' and data:
                    # JSON-RPC Response to stdout
                    print(data, flush=True)

                elif event_type == 'ping':
                    # Heartbeat, just acknowledge
                    pass

    async def stdin_reader(self):
        """Read stdin and send to server."""
        def read_line():
            try:
                return sys.stdin.readline()
            except Exception as e:
                log(f"stdin read error: {e}")
                return None

        log("stdin reader started")

        while self.running:
            try:
                line = await self.loop.run_in_executor(self.executor, read_line)

                if not line:
                    log("stdin closed (EOF)")
                    self.running = False
                    break

                line = line.strip()
                if not line:
                    continue

                if self.messages_url is None:
                    log("Warning: received message before endpoint ready, queuing...")
                    await asyncio.sleep(0.1)
                    continue

                try:
                    msg = json.loads(line)
                    async with self.session.post(self.messages_url, json=msg) as resp:
                        if resp.status != 200 and resp.status != 202:
                            log(f"POST failed: HTTP {resp.status}")
                except json.JSONDecodeError as e:
                    log(f"Invalid JSON from stdin: {e}")
                except aiohttp.ClientError as e:
                    log(f"Send error (will retry via reconnect): {e}")
                except Exception as e:
                    log(f"Send error: {type(e).__name__}: {e}")

            except asyncio.CancelledError:
                log("stdin reader cancelled")
                break
            except Exception as e:
                log(f"stdin reader error: {type(e).__name__}: {e}")
                log(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(0.1)  # Prevent tight loop on errors

        log("stdin reader stopped")

    async def run(self):
        """Main run loop."""
        self.loop = asyncio.get_event_loop()

        log("Starting SSE bridge...")

        try:
            await self.connect_sse()
        finally:
            self.running = False

            if self.stdin_task and not self.stdin_task.done():
                self.stdin_task.cancel()
                try:
                    await self.stdin_task
                except asyncio.CancelledError:
                    pass

            if self.session and not self.session.closed:
                await self.session.close()

            self.executor.shutdown(wait=False)
            log("Bridge closed")

async def main():
    bridge = SSEBridge()
    await bridge.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
