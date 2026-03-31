"""
MCP Server for OpenMemory with resilient memory client handling.

Provides 5 standard memory tools: add, search, list, delete, delete_all.
Graph memory is managed automatically by mem0 internals — no direct graph
access via MCP tools needed.
"""

import contextvars
import datetime
import json
import logging
import uuid

import anyio

from app.database import SessionLocal
from app.models import Memory, MemoryAccessLog, MemoryState, MemoryStatusHistory
from app.utils.db import get_user_and_app
from app.utils.memory import get_memory_client
from app.utils.permissions import check_memory_access_permissions
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import Response

# Load environment variables
load_dotenv()

# Initialize MCP
mcp = FastMCP("mem0-mcp-server")

# Don't initialize memory client at import time - do it lazily when needed
def get_memory_client_safe():
    """Get memory client with error handling. Returns None if client cannot be initialized."""
    try:
        return get_memory_client()
    except Exception as e:
        logging.warning(f"Failed to get memory client: {e}")
        return None

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")


@mcp.tool(description="Add a new memory. Called whenever the user shares information about themselves, their preferences, or anything useful for future conversations. Also called when the user asks to remember something. Set infer=False to store verbatim without LLM fact extraction.")
async def add_memories(text: str, infer: bool = True) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            if not app.is_active:
                return f"Error: App {app.name} is currently paused on OpenMemory. Cannot create new memories."
            response = memory_client.add(text, user_id=uid,
                                         metadata={"source_app": "openmemory", "mcp_client": client_name},
                                         infer=infer)
            if isinstance(response, dict) and 'results' in response:
                for result in response['results']:
                    memory_id = uuid.UUID(result['id'])
                    memory = db.query(Memory).filter(Memory.id == memory_id).first()
                    if result['event'] == 'ADD':
                        if not memory:
                            memory = Memory(id=memory_id, user_id=user.id, app_id=app.id,
                                            content=result['memory'], state=MemoryState.active)
                            db.add(memory)
                        else:
                            memory.state = MemoryState.active
                            memory.content = result['memory']
                        history = MemoryStatusHistory(memory_id=memory_id, changed_by=user.id,
                                                      old_state=MemoryState.deleted if memory else None,
                                                      new_state=MemoryState.active)
                        db.add(history)
                    elif result['event'] == 'DELETE':
                        if memory:
                            memory.state = MemoryState.deleted
                            memory.deleted_at = datetime.datetime.now(datetime.UTC)
                            history = MemoryStatusHistory(memory_id=memory_id, changed_by=user.id,
                                                          old_state=MemoryState.active,
                                                          new_state=MemoryState.deleted)
                            db.add(history)
                db.commit()
            return json.dumps(response)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error adding to memory: {e}")
        return f"Error adding to memory: {e}"


@mcp.tool(description="Search through stored memories. Called whenever the user asks anything.")
async def search_memory(query: str) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [m.id for m in user_memories if check_memory_access_permissions(db, m, app.id)]
            filters = {"user_id": uid}
            embeddings = memory_client.embedding_model.embed(query, "search")
            hits = memory_client.vector_store.search(query=query, vectors=embeddings, limit=10, filters=filters)
            allowed = set(str(mid) for mid in accessible_memory_ids) if accessible_memory_ids else None
            results = []
            for h in hits:
                if allowed and (h.id is None or h.id not in allowed):
                    continue
                results.append({"id": h.id, "memory": h.payload.get("data"), "hash": h.payload.get("hash"),
                                 "created_at": h.payload.get("created_at"), "updated_at": h.payload.get("updated_at"),
                                 "score": h.score})
            for r in results:
                if r.get("id"):
                    db.add(MemoryAccessLog(memory_id=uuid.UUID(r["id"]), app_id=app.id, access_type="search",
                                           metadata_={"query": query, "score": r.get("score"), "hash": r.get("hash")}))
            db.commit()
            return json.dumps({"results": results}, indent=2)
        finally:
            db.close()
    except Exception as e:
        logging.exception(e)
        return f"Error searching memory: {e}"


@mcp.tool(description="List all memories in the user's memory")
async def list_memories() -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            memories = memory_client.get_all(user_id=uid)
            filtered_memories = []
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [m.id for m in user_memories if check_memory_access_permissions(db, m, app.id)]
            items = memories.get('results', memories) if isinstance(memories, dict) else memories
            for memory_data in items:
                if 'id' not in memory_data:
                    continue
                memory_id = uuid.UUID(memory_data['id'])
                if memory_id in accessible_memory_ids:
                    db.add(MemoryAccessLog(memory_id=memory_id, app_id=app.id, access_type="list",
                                           metadata_={"hash": memory_data.get('hash')}))
                    filtered_memories.append(memory_data)
            db.commit()
            return json.dumps(filtered_memories, indent=2)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error getting memories: {e}")
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete specific memories by their IDs")
async def delete_memories(memory_ids: list[str]) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            requested_ids = [uuid.UUID(mid) for mid in memory_ids]
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [m.id for m in user_memories if check_memory_access_permissions(db, m, app.id)]
            ids_to_delete = [mid for mid in requested_ids if mid in accessible_memory_ids]
            if not ids_to_delete:
                return "Error: No accessible memories found with provided IDs"
            for memory_id in ids_to_delete:
                try:
                    memory_client.delete(str(memory_id))
                except Exception as e:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {e}")
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in ids_to_delete:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                if memory:
                    memory.state = MemoryState.deleted
                    memory.deleted_at = now
                    db.add(MemoryStatusHistory(memory_id=memory_id, changed_by=user.id,
                                               old_state=MemoryState.active, new_state=MemoryState.deleted))
                    db.add(MemoryAccessLog(memory_id=memory_id, app_id=app.id, access_type="delete",
                                           metadata_={"operation": "delete_by_id"}))
            db.commit()
            return f"Successfully deleted {len(ids_to_delete)} memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [m.id for m in user_memories if check_memory_access_permissions(db, m, app.id)]
            for memory_id in accessible_memory_ids:
                try:
                    memory_client.delete(str(memory_id))
                except Exception as e:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {e}")
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in accessible_memory_ids:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                if memory:
                    memory.state = MemoryState.deleted
                    memory.deleted_at = now
                    db.add(MemoryStatusHistory(memory_id=memory_id, changed_by=user.id,
                                               old_state=MemoryState.active, new_state=MemoryState.deleted))
                    db.add(MemoryAccessLog(memory_id=memory_id, app_id=app.id, access_type="delete_all",
                                           metadata_={"operation": "bulk_delete"}))
            db.commit()
            return "Successfully deleted all memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")
    try:
        async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
            await mcp._mcp_server.run(read_stream, write_stream, mcp._mcp_server.create_initialization_options())
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@mcp_router.post("/messages/")
async def handle_get_message(request: Request):
    return await handle_post_message(request)


@mcp_router.post("/{client_name}/sse/{user_id}/messages/")
async def handle_post_message_route(request: Request):
    return await handle_post_message(request)


async def handle_post_message(request: Request):
    try:
        body = await request.body()
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(message):
            return {}
        await sse.handle_post_message(request.scope, receive, send)
        return {"status": "ok"}
    finally:
        pass


@mcp_router.api_route("/{client_name}/http/{user_id}", methods=["POST", "GET", "DELETE"])
async def handle_streamable_http(request: Request):
    """Streamable HTTP transport (MCP spec 2025-03-26+). Stateless mode."""
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    response_started = False
    response_status = 200
    response_headers: list[tuple[bytes, bytes]] = []
    response_body = bytearray()

    async def capture_send(message):
        nonlocal response_started, response_status
        if message["type"] == "http.response.start":
            response_started = True
            response_status = message["status"]
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    try:
        transport = StreamableHTTPServerTransport(mcp_session_id=None, is_json_response_enabled=True)
        async with anyio.create_task_group() as tg:
            async def run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
                async with transport.connect() as (read_stream, write_stream):
                    task_status.started()
                    await mcp._mcp_server.run(read_stream, write_stream,
                                              mcp._mcp_server.create_initialization_options(), stateless=True)
            await tg.start(run_server)
            await transport.handle_request(request.scope, request.receive, capture_send)
            await transport.terminate()
            tg.cancel_scope.cancel()
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)

    if not response_started:
        return Response(status_code=500, content=b"Transport did not produce a response")

    return Response(content=bytes(response_body), status_code=response_status,
                    headers={k.decode(): v.decode() for k, v in response_headers})


def setup_mcp_server(app: FastAPI):
    mcp._mcp_server.name = "mem0-mcp-server"
    app.include_router(mcp_router)
