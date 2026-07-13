"""Tests for FastAPI server."""
import pytest
from httpx import AsyncClient, ASGITransport
from server.main import app

from .conftest import skip_if_no_keys


@pytest.fixture
async def cl():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestServer:
    async def test_health(self, cl):
        r = await cl.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @skip_if_no_keys
    async def test_chat(self, cl):
        r = await cl.post("/api/chat", json={"message": "Say hi", "user_id": "pytest"})
        assert r.status_code == 200
        d = r.json()
        assert d["response"] or d["reasoning"]

    async def test_chat_empty(self, cl):
        r = await cl.post("/api/chat", json={"message": "", "user_id": "t"})
        assert r.status_code == 422  # Pydantic validation error on empty string

    @skip_if_no_keys
    async def test_session(self, cl):
        await cl.post("/api/chat", json={"message": "hi", "user_id": "pytest_s"})
        r = await cl.get("/api/session/pytest_s")
        assert r.status_code == 200
        assert r.json()["user_id"] == "pytest_s"

    async def test_reset(self, cl):
        r = await cl.post("/api/session/t/reset")
        assert r.json()["status"] == "cleared"

    async def test_tools_list_no_key(self, cl):
        r = await cl.get("/api/tools/list?page=1&page_size=3")
        assert r.status_code in (200, 502)  # 502 if composio key missing

    async def test_frontend(self, cl):
        r = await cl.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "Zen" in r.text

    async def test_health_version(self, cl):
        r = await cl.get("/api/health")
        assert "version" in r.json()
        assert "agents_active" in r.json()

    async def test_health_model(self, cl):
        r = await cl.get("/api/health")
        assert "model" in r.json()
