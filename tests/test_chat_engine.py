"""
对话引擎单元测试 —— test_chat_engine

【覆盖需求】
A1(多轮对话)  A2(流式输出)  A3(全异步)  A4(可配置LLM后端)  A5(会话内切换模型)
G1(超时 + 重试)  E2(Token 统计)
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.chat_engine import ChatEngine
from src.core.config_manager import AppConfig
from src.core.session_manager import SessionManager
from src.models.schemas import Message
from src.storage.sqlite_backend import SQLiteBackend


@pytest.fixture
async def mgr(tmp_sqlite_backend: SQLiteBackend, test_user) -> SessionManager:
    """返回一个绑定测试用户的 SessionManager 实例"""
    return SessionManager(backend=tmp_sqlite_backend, user_id=test_user.id)


@pytest.fixture
def app_config() -> AppConfig:
    return AppConfig()


@pytest.fixture
async def engine(
    mgr: SessionManager,
    app_config: AppConfig,
) -> ChatEngine:
    """返回一个已创建会话的 ChatEngine 实例"""
    await mgr.create_session(model_name="gpt-4o")
    return ChatEngine(session_mgr=mgr, config=app_config)


# =====================================================================
# _build_llm — A4/A5
# =====================================================================


class TestBuildLLM:
    """A4 可配置LLM后端 / A5 会话内切换模型"""

    async def test_build_llm_uses_session_model(
        self,
        engine: ChatEngine,
        mgr: SessionManager,
    ):
        await mgr.update_model("gpt-4o-mini")
        with patch("src.core.chat_engine.ChatOpenAI") as mock_cls:
            engine._build_llm()
            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["model"] == "gpt-4o-mini"

    async def test_build_llm_uses_config_params(
        self,
        engine: ChatEngine,
        mgr: SessionManager,
        app_config: AppConfig,
    ):
        with patch("src.core.chat_engine.ChatOpenAI") as mock_cls:
            engine._build_llm()
            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["max_retries"] == app_config.llm.max_retries
            assert kwargs["timeout"] == app_config.llm.timeout
            assert kwargs["api_key"] == app_config.env.api_key
            assert kwargs["base_url"] == app_config.env.api_base_url


# =====================================================================
# _to_langchain_messages — A1
# =====================================================================


class TestToLangChainMessages:
    """A1 历史消息格式转换"""

    def test_converts_human_role(self):
        from datetime import datetime, timezone

        msgs = [
            Message(id=1, session_id=1, role="human", content="你好",
                    created_at=datetime.now(timezone.utc)),
            Message(id=2, session_id=1, role="ai", content="你好！",
                    created_at=datetime.now(timezone.utc)),
            Message(id=3, session_id=1, role="system", content="你是一个助手",
                    created_at=datetime.now(timezone.utc)),
        ]
        result = ChatEngine._to_langchain_messages(msgs)
        assert len(result) == 3
        assert result[0].type == "human"
        assert result[0].content == "你好"
        assert result[1].type == "ai"
        assert result[1].content == "你好！"
        assert result[2].type == "system"

    def test_empty_history(self):
        assert ChatEngine._to_langchain_messages([]) == []


# =====================================================================
# chat — A1/A2/A3/E2
# =====================================================================


class TestChat:
    """A1 多轮对话 / A2 流式输出 / A3 全异步 / E2 Token 统计"""

    async def test_chat_requires_active_session(self, app_config: AppConfig, mgr: SessionManager):
        """未创建会话时 chat 应抛 RuntimeError"""
        engine = ChatEngine(session_mgr=mgr, config=app_config)
        with pytest.raises(RuntimeError, match="没有当前会话"):
            async for _ in engine.chat("你好"):
                pass

    async def test_chat_streams_and_saves(
        self,
        engine: ChatEngine,
        mgr: SessionManager,
    ):
        """完整一轮对话：流式产出 + 消息持久化"""
        chunks = ["你好！", "我是", "AI助手。"]

        async def fake_astream(_messages):
            for text in chunks:
                chunk = MagicMock()
                chunk.content = text
                chunk.usage_metadata = None
                yield chunk

        with patch.object(engine, "_build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_llm.astream = fake_astream
            mock_build.return_value = mock_llm

            collected = []
            async for token in engine.chat("hi"):
                collected.append(token)

        assert "".join(collected) == "你好！我是AI助手。"
        # 验证用户消息已保存
        messages = await mgr.get_messages()
        assert len(messages) == 2
        assert messages[0].role == "human"
        assert messages[0].content == "hi"
        assert messages[1].role == "ai"
        assert messages[1].content == "你好！我是AI助手。"

    async def test_chat_extracts_usage_metadata(
        self,
        engine: ChatEngine,
        mgr: SessionManager,
    ):
        """astream 最后一条 chunk 的 usage_metadata 应被提取并传给 add_ai_message"""

        async def fake_astream(_messages):
            yield MagicMock(content="回复", usage_metadata=None)
            usage = MagicMock()
            usage.input_tokens = 10
            usage.output_tokens = 20
            yield MagicMock(content="", usage_metadata=usage)

        with patch.object(engine, "_build_llm") as mock_build:
            mock_llm = MagicMock()
            mock_llm.astream = fake_astream
            mock_build.return_value = mock_llm

            async for _ in engine.chat("hi"):
                pass

        messages = await mgr.get_messages()
        ai_msg = messages[1]
        assert ai_msg.prompt_tokens == 10
        assert ai_msg.completion_tokens == 20


# =====================================================================
# switch_model — A5
# =====================================================================


class TestSwitchModel:
    """A5 会话内切换模型"""

    async def test_switch_model_updates_session(
        self,
        engine: ChatEngine,
        mgr: SessionManager,
    ):
        await engine.switch_model("claude-3")
        assert mgr.current_session is not None
        assert mgr.current_session.model_name == "claude-3"

    async def test_switch_model_persists(
        self,
        engine: ChatEngine,
        mgr: SessionManager,
    ):
        session_id = mgr.current_session.id
        await engine.switch_model("claude-3")
        # 重新加载后仍为切换后的模型
        mgr2 = SessionManager(backend=mgr._backend, user_id=mgr._user_id)
        loaded = await mgr2.load_session(session_id)
        assert loaded.model_name == "claude-3"
