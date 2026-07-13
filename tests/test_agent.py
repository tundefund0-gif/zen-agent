"""Tests for ZenAgent orchestration."""
import pytest
from core.agent import ZenAgent
from core.llm_client import LLMResponse


class TestAgent:
    @pytest.fixture
    def a(self):
        return ZenAgent("pytest_agent", enable_sandbox=False)

    def test_init(self, a):
        i = a.get_info()
        assert i["session_id"]
        assert i["user_id"] == "pytest_agent"

    def test_chat(self, a):
        r = a.chat("Say hello in one word")
        assert isinstance(r, LLMResponse)
        assert r.content.strip()

    def test_chat_empty_raises(self, a):
        with pytest.raises(ValueError):
            a.chat("")

    def test_history(self, a):
        a.chat("msg1")
        a.chat("msg2")
        assert len(a.get_history()) == 4

    def test_clear(self, a):
        a.chat("msg")
        a.clear_history()
        assert len(a.get_history()) == 0

    def test_info(self, a):
        i = a.get_info()
        assert all(k in i for k in ["user_id", "session_id", "message_count"])

    def test_streaming(self, a):
        tokens = list(a.chat("Say hi", stream=True))
        assert len(tokens) > 0
        assert "".join(tokens).strip()

    def test_tool_exec(self, a):
        r = a._exec_composio("COMPOSIO_SEARCH_TOOLS", {"queries": [{"use_case": "test"}]})
        assert r is not None

    def test_trim_history(self, a):
        for i in range(10):
            a.chat(f"message {i}")
        hist = a.get_history()
        assert len(hist) <= 200  # max_history * 2

    def test_session_reuse(self, a):
        a2 = ZenAgent("pytest_agent", session_id=a.session_id, enable_sandbox=False)
        assert a2.session_id == a.session_id

    def test_info_structure(self, a):
        i = a.get_info()
        assert isinstance(i["sandbox_enabled"], bool)
        assert isinstance(i["message_count"], int)
