"""Zen Agent — FastAPI server with REST + WebSocket streaming, middleware, and tool management."""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import config
from core.agent import ZenAgent
from core.composio_client import ComposioClient, ComposioAPIError
from core.llm_client import LLMResponse

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("zen-server")

# ── Agent store ───────────────────────────────────────────────────────
agents: Dict[str, ZenAgent] = {}
_agent_lock = False


def get_agent(user_id: str, session_id: Optional[str] = None) -> ZenAgent:
    if user_id in agents:
        a = agents[user_id]
        if session_id and a.session_id != session_id:
            a = ZenAgent(user_id=user_id, session_id=session_id)
            agents[user_id] = a
        return a
    a = ZenAgent(user_id=user_id, session_id=session_id)
    agents[user_id] = a
    return a


def cleanup_agents():
    while len(agents) > 100:
        agents.pop(next(iter(agents)), None)


# ── Models ────────────────────────────────────────────────────────────
class ChatReq(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    user_id: str = "web-user"
    session_id: Optional[str] = None


class ChatResp(BaseModel):
    response: str
    reasoning: str = ""
    session_id: str
    user_id: str
    tool_calls: List[Dict[str, Any]] = []


class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    sandbox_enabled: bool
    toolkits: Optional[List[str]]
    message_count: int


# ── Lifespan ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Zen Agent server starting on %s:%d", config.host, config.port)
    yield
    logger.info("Zen Agent server shutting down")


# ── App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Zen Agent",
    description="AI agent with 23,790+ Composio tools",
    version="3.0.0",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.time() - start:.3f}s"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info("%s %s -> %d (%.2fs)", request.method, request.url.path, response.status_code, duration)
    return response


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ── Exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── REST API ──────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "3.0.0",
        "model": config.opencode_model,
        "composio": "configured" if config.has_composio_key else "missing",
        "agents_active": len(agents),
        "uptime": time.time(),
    }


@app.post("/api/chat", response_model=ChatResp)
async def chat(req: ChatReq):
    if not req.message.strip():
        raise HTTPException(400, "Message required")
    agent = get_agent(req.user_id, req.session_id)
    try:
        resp = agent.chat(req.message)
        if not isinstance(resp, LLMResponse):
            raise HTTPException(500, "Internal error")
        return ChatResp(
            response=resp.content or "",
            reasoning=resp.reasoning[:2000] if resp.reasoning else "",
            session_id=agent.session_id or "",
            user_id=req.user_id,
            tool_calls=[
                {"name": tc["function"]["name"], "args": tc["function"]["arguments"]}
                for tc in (resp.tool_calls or [])
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(500, str(e))


@app.get("/api/session/{user_id}", response_model=SessionInfo)
async def get_session(user_id: str):
    agent = get_agent(user_id)
    i = agent.get_info()
    return SessionInfo(
        session_id=i["session_id"],
        user_id=i["user_id"],
        sandbox_enabled=i["sandbox_enabled"],
        toolkits=i["toolkits"],
        message_count=i["message_count"],
    )


@app.post("/api/session/{user_id}/reset")
async def reset_session(user_id: str):
    if user_id in agents:
        agents[user_id].clear_history()
    return {"status": "cleared"}


@app.get("/api/tools/list")
async def list_tools(page: int = 1, page_size: int = 20):
    try:
        return ComposioClient().list_all_tools(page=page, page_size=page_size)
    except ComposioAPIError as e:
        raise HTTPException(502, str(e))


@app.get("/api/tools/search")
async def search_tools(query: str, user_id: str = "web-user"):
    agent = get_agent(user_id)
    try:
        return agent._composio.search_tools(agent.session_id, query)
    except ComposioAPIError as e:
        raise HTTPException(502, str(e))


# ── WebSocket streaming ───────────────────────────────────────────────
@app.websocket("/ws/chat/{user_id}")
async def ws_chat(websocket: WebSocket, user_id: str):
    await websocket.accept()
    agent = get_agent(user_id)
    await websocket.send_json({
        "type": "info",
        "session_id": agent.session_id,
        "user_id": user_id,
    })
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg = data.get("message", "")
            except json.JSONDecodeError:
                msg = raw
            if not msg.strip():
                continue
            if msg.strip().lower() == "/clear":
                agent.clear_history()
                await websocket.send_json({"type": "clear"})
                continue
            full = ""
            try:
                async for token in _stream_agent(agent, msg):
                    if token.startswith("__reasoning__"):
                        await websocket.send_json({
                            "type": "reasoning",
                            "content": token[13:],
                        })
                    else:
                        full += token
                        await websocket.send_json({"type": "token", "content": token})
                await websocket.send_json({"type": "done", "content": full})
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
                logger.exception("WS stream error")
    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", user_id)
    except Exception as e:
        logger.exception("WS error")


async def _stream_agent(agent: ZenAgent, message: str):
    """Async wrapper around the sync agent stream generator."""
    for token in agent.chat(message, stream=True):
        yield token


# ── Frontend ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    p = os.path.join(static_dir, "index.html")
    if os.path.isfile(p):
        with open(p) as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Zen Agent</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level,
        ws_ping_interval=30,
        ws_ping_timeout=10,
    )
