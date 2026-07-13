"""Composio REST API client — direct HTTP, no SDK dependency, with retry & connection pooling."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from config import config

logger = logging.getLogger("zen-agent.composio")


class ComposioAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        self.status_code = status_code
        self.body = body
        super().__init__(message)

    def __str__(self) -> str:
        base = self.args[0] if self.args else "Composio API error"
        if self.status_code:
            base += f" [HTTP {self.status_code}]"
        return base


class ComposioClient:
    """Direct wrapper around Composio REST API v3/v3.1 with connection pooling & retry."""

    def __init__(self, api_key: Optional[str] = None, timeout: Optional[int] = None):
        self.api_key = api_key or config.composio_api_key
        self.base_url = config.composio_base_url.rstrip("/")
        self.timeout = timeout or config.composio_timeout
        self._pool: Optional[httpx.Client] = None

    @property
    def pool(self) -> httpx.Client:
        if self._pool is None:
            self._pool = httpx.Client(
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "ZenAgent/1.0",
                },
                timeout=httpx.Timeout(self.timeout, connect=15.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._pool

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        ctx: str = "",
        retries: int = 3,
    ) -> Any:
        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                r = self.pool.request(method, url, json=json_body, params=params)
                return self._handle(r, ctx)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning("Composio request failed (attempt %d/%d), retrying in %ds: %s", attempt, retries, wait, e)
                    time.sleep(wait)
                else:
                    raise ComposioAPIError(f"Composio unavailable after {retries} retries: {e}") from e

    # ── Sessions ──────────────────────────────────────────────────────
    def create_session(self, user_id: str, toolkits: Optional[List[str]] = None, sandbox: bool = False) -> Dict[str, Any]:
        body: Dict[str, Any] = {"user_id": user_id}
        if toolkits:
            body["toolkits"] = {"enable": toolkits}
        if sandbox:
            body["workbench"] = {"enable": True}
        return self._request("POST", "/api/v3.1/tool_router/session", json_body=body, ctx="create session")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v3.1/tool_router/session/{session_id}", ctx="get session")

    def delete_session(self, session_id: str) -> Dict[str, Any]:
        return self._request("DELETE", f"/api/v3.1/tool_router/session/{session_id}", ctx="delete session")

    # ── Tool execution ────────────────────────────────────────────────
    def execute_tool(self, session_id: str, tool_slug: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = {"tool_slug": tool_slug, "arguments": arguments or {}}
        return self._request("POST", f"/api/v3.1/tool_router/session/{session_id}/execute", json_body=body, ctx="execute tool")

    def execute_meta(self, session_id: str, action: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.execute_tool(session_id, tool_slug=action, arguments=arguments)

    # ── Tool discovery ────────────────────────────────────────────────
    def search_tools(self, session_id: str, use_case: str) -> Dict[str, Any]:
        return self.execute_meta(session_id, "COMPOSIO_SEARCH_TOOLS", {"queries": [{"use_case": use_case}]})

    def get_tools(self, session_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v3.1/tool_router/session/{session_id}/tools", ctx="get tools")

    def get_tool_schemas(self, session_id: str, tool_slugs: List[str]) -> Dict[str, Any]:
        return self.execute_meta(session_id, "COMPOSIO_GET_TOOL_SCHEMAS", {"tool_slugs": tool_slugs})

    def list_all_tools(self, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        return self._request("GET", "/api/v3/tools", params={"page": page, "pageSize": page_size}, ctx="list tools")

    # ── Auth / connections ────────────────────────────────────────────
    def manage_connections(self, session_id: str, toolkits: List[str], reinitiate: bool = False) -> Dict[str, Any]:
        return self.execute_meta(session_id, "COMPOSIO_MANAGE_CONNECTIONS", {"toolkits": toolkits, "reinitiate_all": reinitiate})

    def link_account(self, session_id: str, toolkit: str) -> Dict[str, Any]:
        return self.manage_connections(session_id, [toolkit])

    # ── Sandbox / multi ───────────────────────────────────────────────
    def execute_workbench(self, session_id: str, code: str) -> Dict[str, Any]:
        return self.execute_meta(session_id, "COMPOSIO_REMOTE_WORKBENCH", {"code": code, "language": "python"})

    def execute_bash(self, session_id: str, command: str) -> Dict[str, Any]:
        return self.execute_meta(session_id, "COMPOSIO_REMOTE_BASH_TOOL", {"cmd": command})

    def multi_execute(self, session_id: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.execute_meta(session_id, "COMPOSIO_MULTI_EXECUTE_TOOL", {"tools": tools})

    # ── Proxy ─────────────────────────────────────────────────────────
    def proxy_execute(self, session_id: str, endpoint: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"endpoint": endpoint, "method": method}
        if headers:
            payload["headers"] = headers
        if body:
            payload["body"] = body
        return self._request("POST", f"/api/v3.1/tool_router/session/{session_id}/proxy_execute", json_body=payload, ctx="proxy execute")

    # ── Config history ────────────────────────────────────────────────
    def config_history(self, session_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/api/v3.1/tool_router/session/{session_id}/config_history", ctx="config history")

    # ── Internal ──────────────────────────────────────────────────────
    @staticmethod
    def _handle(resp: httpx.Response, ctx: str) -> Dict[str, Any]:
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise ComposioAPIError(
                f"Composio API error ({ctx})", status_code=resp.status_code, body=body
            )
        try:
            return resp.json()
        except Exception as e:
            raise ComposioAPIError(f"Invalid JSON ({ctx}): {e}")

    def close(self):
        if self._pool:
            self._pool.close()
            self._pool = None
