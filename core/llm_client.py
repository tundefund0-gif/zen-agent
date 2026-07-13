"""OpenAI-compatible LLM client for OpenCode API with full reasoning, streaming & retry support."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional, Union

import httpx

from config import config

logger = logging.getLogger("zen-agent.llm")


class LLMError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        self.status_code = status_code
        self.body = body
        super().__init__(message)


class LLMResponse:
    """Wraps a chat completion response for easy access."""
    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        self.choice = raw.get("choices", [{}])[0]
        self.message = self.choice.get("message", {})
        self.content: str = self.message.get("content", "") or ""
        self.reasoning: str = self.message.get("reasoning_content", "") or ""
        self.finish_reason: str = self.choice.get("finish_reason", "")
        self.model: str = raw.get("model", "")
        self.usage: Dict = raw.get("usage", {})
        self.tool_calls = self.message.get("tool_calls")

    def __repr__(self) -> str:
        tc = len(self.tool_calls) if self.tool_calls else 0
        return f"LLMResponse(model={self.model}, content_len={len(self.content)}, tools={tc})"


class LLMClient:
    """Client for OpenAI-compatible chat completion APIs (OpenCode) with retry & connection pooling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        self.api_key = api_key or config.opencode_api_key
        self.base_url = (base_url or config.opencode_base_url).rstrip("/")
        self.model = model or config.opencode_model
        self.max_tokens = max_tokens or config.opencode_max_tokens
        self.timeout = timeout or config.opencode_timeout
        self._pool: Optional[httpx.Client] = None

    @property
    def pool(self) -> httpx.Client:
        if self._pool is None:
            self._pool = httpx.Client(
                timeout=httpx.Timeout(self.timeout, connect=30.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                headers=self._headers(),
            )
        return self._pool

    def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        stream: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Union[LLMResponse, Generator[str, None, None]]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        if stream:
            return self._stream(body)
        return self._sync_with_retry(body)

    def _sync_with_retry(self, body: Dict[str, Any], retries: int = 3) -> LLMResponse:
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                return self._sync(body)
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning("LLM request failed (attempt %d/%d), retrying in %ds: %s", attempt, retries, wait, e)
                    time.sleep(wait)
                else:
                    raise LLMError(f"LLM API unavailable after {retries} retries: {e}") from e
            except LLMError:
                raise

    def _sync(self, body: Dict[str, Any]) -> LLMResponse:
        r = self.pool.post(f"{self.base_url}/chat/completions", json=body)
        if r.status_code >= 400:
            try:
                d = r.json()
            except Exception:
                d = r.text
            raise LLMError(f"LLM API error: HTTP {r.status_code}", status_code=r.status_code, body=d)
        return LLMResponse(r.json())

    def _stream(self, body: Dict[str, Any]) -> Generator[str, None, None]:
        with httpx.Client(
            timeout=httpx.Timeout(self.timeout, connect=30.0),
            headers=self._headers(),
        ) as cl:
            with cl.stream("POST", f"{self.base_url}/chat/completions", json=body) as r:
                if r.status_code >= 400:
                    try:
                        d = r.json()
                    except Exception:
                        d = r.text
                    raise LLMError(f"LLM API error: HTTP {r.status_code}", status_code=r.status_code, body=d)
                for line in r.iter_lines():
                    if not line or line.startswith(":keep-alive"):
                        continue
                    if line.startswith("data: "):
                        d = line[6:].strip()
                        if d == "[DONE]":
                            break
                        try:
                            chunk = json.loads(d)
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            rc = delta.get("reasoning_content", "")
                            if rc:
                                yield f"__reasoning__{rc}"
                            c = delta.get("content", "")
                            if c:
                                yield c
                        except json.JSONDecodeError:
                            continue

    def complete(self, prompt: str, system: Optional[str] = None) -> str:
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages).content

    def count_tokens(self, text: str) -> int:
        """Rough token count estimate."""
        return len(text) // 4 + 1

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ZenAgent/1.0",
        }

    def close(self):
        if self._pool:
            self._pool.close()
            self._pool = None
