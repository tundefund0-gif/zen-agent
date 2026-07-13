"""Tests for LLM client with retry and connection pooling."""
import pytest
from core.llm_client import LLMClient, LLMError


class TestLLM:
    @pytest.fixture
    def llm(self):
        return LLMClient(max_tokens=200)

    @pytest.fixture
    def llm_big(self):
        return LLMClient(max_tokens=500)

    def test_basic(self, llm):
        r = llm.chat([{"role": "user", "content": "Say hi"}])
        assert r.content or r.reasoning

    def test_reasoning(self, llm_big):
        r = llm_big.chat([{"role": "user", "content": "Say hello"}])
        assert r.reasoning or r.content

    def test_streaming(self, llm):
        tokens = []
        for t in llm.chat([{"role": "user", "content": "Count 1 2 3"}], stream=True):
            tokens.append(t)
            if len(tokens) > 15:
                break
        assert len(tokens) > 0

    def test_complete(self, llm_big):
        r = llm_big.complete("Say 'test'")
        assert r.strip()

    def test_invalid_model(self):
        with pytest.raises(LLMError):
            LLMClient(model="bad-model-nonexistent", max_tokens=50).chat([{"role": "user", "content": "hi"}])

    def test_count_tokens(self, llm):
        assert llm.count_tokens("hello world") > 0

    def test_close(self, llm):
        llm.close()
        assert llm._pool is None

    def test_system_prompt(self, llm):
        r = llm.chat([{"role": "system", "content": "Say only 'ok'"}, {"role": "user", "content": "hi"}])
        assert r.content.strip()

    def test_llm_response_repr(self, llm):
        r = llm.chat([{"role": "user", "content": "Say hi"}])
        assert "LLMResponse" in repr(r)
