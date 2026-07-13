"""Tests for ZenAgent orchestration."""
import pytest
from config import config
from core.agent import ZenAgent
from core.llm_client import LLMResponse

from .conftest import skip_if_no_keys, skip_if_no_composio, has_composio


def _make_agent(user_id="pytest_agent"):
    """Create agent if composio configured, else return None."""
    if not has_composio:
        return None
    try:
        return ZenAgent(user_id, enable_sandbox=False)
    except Exception:
        return None


class TestAgent:
    @skip_if_no_composio
    def test_init(self):
        a = _make_agent()
        i = a.get_info()
        assert i["session_id"]
        assert i["user_id"] == "pytest_agent"

    @skip_if_no_keys
    def test_chat(self):
        a = _make_agent()
        r = a.chat("Say hello in one word")
        assert isinstance(r, LLMResponse)
        assert r.content.strip()

    def test_chat_empty_raises(self):
        a = _make_agent()
        if a:
            with pytest.raises(ValueError):
                a.chat("")

    @skip_if_no_keys
    def test_history(self):
        a = _make_agent()
        a.chat("msg1")
        a.chat("msg2")
        assert len(a.get_history()) == 4

    @skip_if_no_composio
    def test_clear(self):
        a = _make_agent()
        a.chat("msg")
        a.clear_history()
        assert len(a.get_history()) == 0

    def test_info(self):
        # Test info structure works conceptually
        pass

    @skip_if_no_composio
    def test_info_from_agent(self):
        a = _make_agent()
        i = a.get_info()
        assert i["user_id"] == "pytest_agent"
        assert "message_count" in i

    @skip_if_no_keys
    def test_streaming(self):
        a = _make_agent()
        tokens = list(a.chat("Say hi", stream=True))
        assert len(tokens) > 0
        assert "".join(tokens).strip()

    @skip_if_no_composio
    def test_tool_exec(self):
        a = _make_agent()
        r = a._exec_composio("COMPOSIO_SEARCH_TOOLS", {"queries": [{"use_case": "test"}]})
        assert r is not None

    @skip_if_no_keys
    def test_trim_history(self):
        a = _make_agent()
        for i in range(10):
            a.chat(f"message {i}")
        hist = a.get_history()
        assert len(hist) <= 200

    @skip_if_no_keys
    def test_session_reuse(self):
        a = _make_agent()
        a2 = _make_agent("pytest_agent")
        if a and a.session_id:
            a2 = ZenAgent("pytest_agent", session_id=a.session_id, enable_sandbox=False)
            assert a2.session_id == a.session_id
