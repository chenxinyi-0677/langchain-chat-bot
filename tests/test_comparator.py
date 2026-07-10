"""
多模型对比单元测试 —— test_comparator

【覆盖需求】
H2(多模型并行对比)

【Why】
Comparator 涉及 LLM 并发调用、错误隔离，需通过 mock 验证。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.comparator import Comparator, ModelResult


@pytest.fixture
def app_config():
    """返回最小 AppConfig（mock 模式只需要 env.xxx 字段）"""
    config = MagicMock()
    config.env.api_key = "sk-test"
    config.env.api_base_url = "https://test.api.com"
    config.llm.timeout = 10
    config.llm.max_retries = 0
    return config


class TestModelResult:
    """ModelResult 数据类"""

    def test_defaults(self):
        r = ModelResult(model_name="gpt-4o")
        assert r.model_name == "gpt-4o"
        assert r.response == ""
        assert r.prompt_tokens == 0
        assert r.completion_tokens == 0
        assert r.error is None

    def test_with_error(self):
        r = ModelResult(model_name="m", error="timeout")
        assert r.error == "timeout"


class TestCompare:
    """compare() 并发与错误隔离"""

    async def test_compare_returns_results_for_all_models(self, app_config):
        """正常调用应为每个模型返回一个 ModelResult"""
        c = Comparator(config=app_config)

        async def empty_astream(_):
            return
            yield  # make it a generator

        mock_llm = AsyncMock()
        mock_llm.astream = empty_astream
        with patch.object(c, "_build_llm", return_value=mock_llm):
            results = await c.compare("hello", ["gpt-4o", "claude-3"])
        assert len(results) == 2
        assert all(isinstance(r, ModelResult) for r in results)

    async def test_one_model_failure_does_not_block_others(self, app_config):
        """一个模型抛异常应只影响自己，其他模型正常返回"""
        c = Comparator(config=app_config)

        async def fake_astream(_):
            chunk = MagicMock()
            chunk.content = "ok"
            chunk.usage_metadata = None
            yield chunk

        def side_effect(model_name):
            if model_name == "broken":
                raise RuntimeError("API error")
            mock = AsyncMock()
            mock.astream = fake_astream
            return mock

        with patch.object(c, "_build_llm", side_effect=side_effect):
            results = await c.compare("hi", ["broken", "working"])

        assert len(results) == 2
        assert results[0].model_name == "broken"
        assert results[0].error is not None
        assert "API error" in results[0].error
        assert results[1].model_name == "working"
        assert results[1].error is None
        assert results[1].response == "ok"

    async def test_empty_model_list(self, app_config):
        """空模型列表应返回空列表"""
        c = Comparator(config=app_config)
        results = await c.compare("hello", [])
        assert results == []
