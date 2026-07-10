"""
会话管理单元测试 —— test_session_manager

【覆盖需求】
C1(新建会话)  C2(加载历史会话)  C3(会话列表)  C4(重命名)
C5(删除会话)  C6(自动保存)  C7(标题自动生成)  E1(对话搜索)  E2(Token 统计)  B4(用户隔离)
"""

from unittest.mock import AsyncMock

import pytest

from src.core.session_manager import SessionManager
from src.models.schemas import User, UserCreate
from src.storage.sqlite_backend import SQLiteBackend


@pytest.fixture
async def mgr(tmp_sqlite_backend: SQLiteBackend, test_user: User) -> SessionManager:
    """返回一个已绑定测试用户的 SessionManager 实例"""
    return SessionManager(backend=tmp_sqlite_backend, user_id=test_user.id)


# =====================================================================
# C1 — 新建会话
# =====================================================================


class TestCreateSession:
    """C1 新建会话"""

    async def test_create_session_sets_current(self, mgr: SessionManager):
        session = await mgr.create_session(model_name="gpt-4o")
        assert session.id == 1
        assert mgr.current_session is not None
        assert mgr.current_session.id == session.id

    async def test_create_session_with_preset(
        self,
        mgr: SessionManager,
        tmp_sqlite_backend: SQLiteBackend,
        test_user: User,
    ):
        preset = await tmp_sqlite_backend.create_preset(
            self._preset_factory(name="助手", system_prompt="你是一个助手"),
        )
        session = await mgr.create_session(model_name="gpt-4o", preset_id=preset.id)
        assert session.preset_id == preset.id

    async def test_create_session_title_none(self, mgr: SessionManager):
        session = await mgr.create_session(model_name="gpt-4o")
        assert session.title == "未命名会话"

    async def test_title_generated_flag_not_set(self, mgr: SessionManager):
        """新建会话后 _title_generated 应为 False"""
        await mgr.create_session(model_name="gpt-4o")
        assert mgr._title_generated is False

    @staticmethod
    def _preset_factory(name: str, system_prompt: str):
        from src.models.schemas import PresetCreate

        return PresetCreate(name=name, system_prompt=system_prompt)


# =====================================================================
# C2 — 加载历史会话
# =====================================================================


class TestLoadSession:
    """C2 加载历史会话"""

    async def test_load_existing_session(self, mgr: SessionManager):
        created = await mgr.create_session(model_name="gpt-4o")
        mgr2 = SessionManager(backend=mgr._backend, user_id=mgr._user_id)
        loaded = await mgr2.load_session(created.id)
        assert loaded.id == created.id
        assert mgr2.current_session is not None

    async def test_load_session_wrong_user_raises(self, mgr: SessionManager, tmp_sqlite_backend: SQLiteBackend):
        # 创建另一个用户
        other = await tmp_sqlite_backend.create_user(
            self._user_factory(username="other"),
        )
        other_mgr = SessionManager(backend=tmp_sqlite_backend, user_id=other.id)
        session = await mgr.create_session(model_name="gpt-4o")
        with pytest.raises(ValueError, match="不属于当前用户"):
            await other_mgr.load_session(session.id)

    async def test_load_nonexistent_session_raises(self, mgr: SessionManager):
        with pytest.raises(ValueError, match="不存在"):
            await mgr.load_session(999)

    async def test_load_sets_title_generated_if_has_human(self, mgr: SessionManager):
        """加载有 human 消息的会话时 _title_generated 应为 True"""
        session = await mgr.create_session(model_name="gpt-4o")
        await mgr.add_user_message("你好")
        # 重新加载
        mgr2 = SessionManager(backend=mgr._backend, user_id=mgr._user_id)
        await mgr2.load_session(session.id)
        assert mgr2._title_generated is True

    async def test_load_empty_session_title_not_generated(self, mgr: SessionManager):
        """加载无消息的会话时 _title_generated 应为 False"""
        session = await mgr.create_session(model_name="gpt-4o")
        mgr2 = SessionManager(backend=mgr._backend, user_id=mgr._user_id)
        await mgr2.load_session(session.id)
        assert mgr2._title_generated is False

    @staticmethod
    def _user_factory(username: str):
        from src.models.schemas import UserCreate

        return UserCreate(username=username)


# =====================================================================
# C3 — 会话列表
# =====================================================================


class TestListSessions:
    """C3 会话列表"""

    async def test_list_sessions_returns_user_sessions(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o", preset_id=None)
        await mgr.create_session(model_name="gpt-4o", preset_id=None)
        sessions = await mgr.list_sessions()
        assert len(sessions) == 2

    async def test_list_sessions_excludes_other_users(
        self,
        mgr: SessionManager,
        tmp_sqlite_backend: SQLiteBackend,
        test_user: User,
    ):
        await mgr.create_session(model_name="gpt-4o")
        other = await tmp_sqlite_backend.create_user(
            UserCreate(username="other"),
        )
        other_mgr = SessionManager(backend=tmp_sqlite_backend, user_id=other.id)
        await other_mgr.create_session(model_name="gpt-4o")
        assert len(await mgr.list_sessions()) == 1


# =====================================================================
# C4 — 重命名
# =====================================================================


class TestRenameSession:
    """C4 重命名"""

    async def test_rename_session(self, mgr: SessionManager):
        session = await mgr.create_session(model_name="gpt-4o")
        updated = await mgr.rename_session(session.id, "新标题")
        assert updated.title == "新标题"

    async def test_rename_updates_cache(self, mgr: SessionManager):
        session = await mgr.create_session(model_name="gpt-4o")
        await mgr.rename_session(session.id, "新标题")
        assert mgr.current_session is not None
        assert mgr.current_session.title == "新标题"

    async def test_rename_wrong_user_raises(self, mgr: SessionManager, tmp_sqlite_backend: SQLiteBackend):
        session = await mgr.create_session(model_name="gpt-4o")
        other = await tmp_sqlite_backend.create_user(
            UserCreate(username="other"),
        )
        other_mgr = SessionManager(backend=tmp_sqlite_backend, user_id=other.id)
        with pytest.raises(ValueError, match="不属于当前用户"):
            await other_mgr.rename_session(session.id, "hack")

    async def test_rename_sets_title_generated(self, mgr: SessionManager):
        """手动重命名后 _title_generated 应为 True"""
        await mgr.create_session(model_name="gpt-4o")
        await mgr.rename_session(mgr.current_session.id, "手动标题")
        assert mgr._title_generated is True


# =====================================================================
# A5 — 切换模型
# =====================================================================


class TestUpdateModel:
    """A5 切换模型"""

    async def test_update_model(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        updated = await mgr.update_model("gpt-4o-mini")
        assert updated.model_name == "gpt-4o-mini"
        # 内存缓存同步更新
        assert mgr.current_session is not None
        assert mgr.current_session.model_name == "gpt-4o-mini"

    async def test_update_model_persists(self, mgr: SessionManager):
        session = await mgr.create_session(model_name="gpt-4o")
        await mgr.update_model("claude-3")
        # 重新加载后仍为切换后的模型
        mgr2 = SessionManager(backend=mgr._backend, user_id=mgr._user_id)
        loaded = await mgr2.load_session(session.id)
        assert loaded.model_name == "claude-3"

    async def test_update_model_no_session_raises(self, mgr: SessionManager):
        with pytest.raises(RuntimeError, match="没有当前会话"):
            await mgr.update_model("gpt-4o")


# =====================================================================
# C5 — 删除会话
# =====================================================================


class TestDeleteSession:
    """C5 删除会话"""

    async def test_delete_session(self, mgr: SessionManager):
        session = await mgr.create_session(model_name="gpt-4o")
        await mgr.delete_session(session.id)
        assert await mgr._backend.get_session(session.id) is None
        assert mgr.current_session is None
        assert mgr._title_generated is False

    async def test_delete_wrong_user_raises(self, mgr: SessionManager, tmp_sqlite_backend: SQLiteBackend):
        session = await mgr.create_session(model_name="gpt-4o")
        other = await tmp_sqlite_backend.create_user(
            UserCreate(username="other"),
        )
        other_mgr = SessionManager(backend=tmp_sqlite_backend, user_id=other.id)
        with pytest.raises(ValueError, match="不属于当前用户"):
            await other_mgr.delete_session(session.id)


# =====================================================================
# C7 — 标题自动生成
# =====================================================================


class TestAutoTitle:
    """C7 标题自动生成"""

    async def test_first_human_message_generates_title(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        msg = await mgr.add_user_message("今天天气怎么样？")
        assert msg.role == "human"
        # 标题应取前 30 字符
        assert mgr.current_session is not None
        assert mgr.current_session.title == "今天天气怎么样？"

    async def test_second_human_message_does_not_change_title(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        await mgr.add_user_message("第一条消息")
        title_after_first = mgr.current_session.title  # type: ignore[union-attr]
        await mgr.add_user_message("第二条消息")
        assert mgr.current_session is not None
        assert mgr.current_session.title == title_after_first

    async def test_ai_message_does_not_trigger_title(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        await mgr.add_ai_message("AI 回复")
        # AI 消息不应触发标题生成，title 仍为占位符
        assert mgr.current_session is not None
        assert mgr.current_session.title == "未命名会话"
        assert mgr._title_generated is False

    async def test_title_generated_flag_set_after_first_human(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        await mgr.add_user_message("测试")
        assert mgr._title_generated is True

    async def test_title_truncated_to_30_chars(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        long_msg = "这是" * 20  # 40 chars
        await mgr.add_user_message(long_msg)
        assert mgr.current_session is not None
        assert len(mgr.current_session.title) == 30
        assert mgr.current_session.title == long_msg[:30]


# =====================================================================
# E2 — Token 累计
# =====================================================================


class TestTokenAccumulation:
    """E2 Token 用量统计"""

    async def test_token_accumulates_across_messages(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        await mgr.add_user_message("hi", prompt_tokens=10)
        await mgr.add_ai_message("hello", prompt_tokens=20, completion_tokens=50)
        prompt, completion = mgr.current_token_usage
        assert prompt == 30
        assert completion == 50

    async def test_token_zero_when_no_session(self, mgr: SessionManager):
        prompt, completion = mgr.current_token_usage
        assert prompt == 0
        assert completion == 0

    async def test_token_usage_from_database(self, mgr: SessionManager):
        """验证 token 累计已持久化到数据库"""
        session = await mgr.create_session(model_name="gpt-4o")
        await mgr.add_user_message("hi", prompt_tokens=10)
        await mgr.add_ai_message("hello", completion_tokens=50)

        # 重新加载，从数据库读取
        mgr2 = SessionManager(backend=mgr._backend, user_id=mgr._user_id)
        await mgr2.load_session(session.id)
        prompt, completion = mgr2.current_token_usage
        assert prompt == 10
        assert completion == 50


# =====================================================================
# get_messages
# =====================================================================


class TestGetMessages:
    """获取历史消息"""

    async def test_get_messages(self, mgr: SessionManager):
        await mgr.create_session(model_name="gpt-4o")
        m1 = await mgr.add_user_message("hi")
        m2 = await mgr.add_ai_message("hello")
        messages = await mgr.get_messages()
        assert len(messages) == 2
        assert messages[0].id == m1.id
        assert messages[1].id == m2.id

    async def test_get_messages_no_session_raises(self, mgr: SessionManager):
        with pytest.raises(RuntimeError, match="没有当前会话"):
            await mgr.get_messages()

    async def test_add_message_no_session_raises(self, mgr: SessionManager):
        with pytest.raises(RuntimeError, match="没有当前会话"):
            await mgr.add_user_message("hi")
        with pytest.raises(RuntimeError, match="没有当前会话"):
            await mgr.add_ai_message("hello")


# =====================================================================
# E1 — 对话搜索
# =====================================================================


class TestSearchMessages:
    """E1 搜索 —— 纯透传，不重复测 storage 层 LIKE 逻辑"""

    async def test_search_delegates_to_backend(self):
        backend = AsyncMock()
        backend.search_messages.return_value = []
        mgr = SessionManager(backend=backend, user_id=42)
        result = await mgr.search_messages("hello")
        backend.search_messages.assert_awaited_once_with(42, "hello")
        assert result == []

    async def test_search_passthrough_results(self):
        backend = AsyncMock()
        backend.search_messages.return_value = [("fake_session", ["fake_msg"])]
        mgr = SessionManager(backend=backend, user_id=1)
        result = await mgr.search_messages("test")
        assert result == [("fake_session", ["fake_msg"])]
