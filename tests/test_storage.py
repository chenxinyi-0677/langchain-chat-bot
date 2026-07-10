"""
存储层集成测试 —— test_storage

【What】
验证 SQLiteBackend 所有 CRUD 方法的正确性，包括级联删除、唯一性约束、
title 兜底、自动建目录等逻辑。

【Why】
确保存储层行为与需求文档 4.1~4.3 节一致，防止重构时引入回归。

【Where】
对应 src/storage/sqlite_backend.py 中 SQLiteBackend 的全部公开方法。
"""

from pathlib import Path

import pytest

from src.models.schemas import (
    MessageCreate,
    PresetCreate,
    SessionCreate,
    UserConfigCreate,
    UserCreate,
)
from src.storage.sqlite_backend import SQLiteBackend

# =========================================================================
# User CRUD
# =========================================================================


class TestUserStorage:
    """用户存储测试"""

    async def test_create_and_get_user(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(
            UserCreate(username="alice", default_model="gpt-4o"),
        )
        assert user.id == 1
        assert user.username == "alice"
        assert user.default_model == "gpt-4o"

        fetched = await tmp_sqlite_backend.get_user(user.id)
        assert fetched is not None
        assert fetched.username == "alice"

    async def test_create_duplicate_username_raises(self, tmp_sqlite_backend: SQLiteBackend):
        await tmp_sqlite_backend.create_user(UserCreate(username="alice"))
        with pytest.raises(ValueError, match="alice"):
            await tmp_sqlite_backend.create_user(UserCreate(username="alice"))

    async def test_get_user_by_username(self, tmp_sqlite_backend: SQLiteBackend):
        await tmp_sqlite_backend.create_user(UserCreate(username="bob"))
        fetched = await tmp_sqlite_backend.get_user_by_username("bob")
        assert fetched is not None
        assert fetched.username == "bob"
        assert await tmp_sqlite_backend.get_user_by_username("nonexistent") is None

    async def test_update_user(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="carol"))
        user.default_model = "gpt-4-turbo"
        updated = await tmp_sqlite_backend.update_user(user)
        assert updated.default_model == "gpt-4-turbo"

    async def test_list_users(self, tmp_sqlite_backend: SQLiteBackend):
        assert await tmp_sqlite_backend.list_users() == []
        await tmp_sqlite_backend.create_user(UserCreate(username="a"))
        await tmp_sqlite_backend.create_user(UserCreate(username="b"))
        users = await tmp_sqlite_backend.list_users()
        assert len(users) == 2

    async def test_delete_user_cascades(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="dave"))
        ses = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, model_name="gpt-4o"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(session_id=ses.id, role="human", content="hi"),
        )
        await tmp_sqlite_backend.delete_user(user.id)
        assert await tmp_sqlite_backend.get_user(user.id) is None
        assert await tmp_sqlite_backend.get_session(ses.id) is None
        msgs = await tmp_sqlite_backend.get_messages_by_session(ses.id)
        assert msgs == []


# =========================================================================
# Session CRUD
# =========================================================================


class TestSessionStorage:
    """会话存储测试"""

    async def test_create_session_title_fallback(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="eve"))
        ses = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, model_name="gpt-4o"),
        )
        assert ses.title == "未命名会话"

    async def test_create_session_with_title(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="f"))
        ses = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, title="我的会话", model_name="gpt-4o"),
        )
        assert ses.title == "我的会话"

    async def test_get_sessions_by_user(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="g"))
        await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, model_name="gpt-4o"),
        )
        sessions = await tmp_sqlite_backend.get_sessions_by_user(user.id)
        assert len(sessions) == 1
        # 其他用户不应看到此会话
        other = await tmp_sqlite_backend.create_user(UserCreate(username="h"))
        assert await tmp_sqlite_backend.get_sessions_by_user(other.id) == []

    async def test_update_session(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="i"))
        ses = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, model_name="gpt-4o"),
        )
        ses.title = "新标题"
        updated = await tmp_sqlite_backend.update_session(ses)
        assert updated.title == "新标题"

    async def test_delete_session_cascades(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="j"))
        ses = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, model_name="gpt-4o"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(session_id=ses.id, role="human", content="msg"),
        )
        await tmp_sqlite_backend.delete_session(ses.id)
        assert await tmp_sqlite_backend.get_session(ses.id) is None
        assert await tmp_sqlite_backend.get_messages_by_session(ses.id) == []


# =========================================================================
# Message CRUD
# =========================================================================


class TestMessageStorage:
    """消息存储测试"""

    async def test_create_and_list_messages(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="k"))
        ses = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, model_name="gpt-4o"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(session_id=ses.id, role="human", content="hello"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(
                session_id=ses.id,
                role="ai",
                content="world",
                prompt_tokens=10,
                completion_tokens=20,
            ),
        )
        msgs = await tmp_sqlite_backend.get_messages_by_session(ses.id)
        assert len(msgs) == 2
        assert msgs[0].content == "hello"
        assert msgs[1].content == "world"
        assert msgs[1].prompt_tokens == 10
        assert msgs[1].completion_tokens == 20

    async def test_search_messages(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="l"))
        s1 = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, title="s1", model_name="gpt-4o"),
        )
        s2 = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, title="s2", model_name="gpt-4o"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(session_id=s1.id, role="human", content="今天天气真好"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(session_id=s2.id, role="ai", content="是的，天气不错"),
        )
        results = await tmp_sqlite_backend.search_messages(user.id, "天气")
        assert len(results) == 2
        # 检查总匹配条数
        total = sum(len(msgs) for _, msgs in results)
        assert total == 2


# =========================================================================
# Preset CRUD
# =========================================================================


class TestPresetStorage:
    """预设存储测试"""

    async def test_create_builtin_preset(self, tmp_sqlite_backend: SQLiteBackend):
        p = await tmp_sqlite_backend.create_preset(
            PresetCreate(name="翻译", system_prompt="翻译以下内容", is_builtin=True),
        )
        assert p.id == 1
        assert p.user_id is None
        assert p.is_builtin is True

    async def test_get_builtin_presets(self, tmp_sqlite_backend: SQLiteBackend):
        await tmp_sqlite_backend.create_preset(
            PresetCreate(name="内置1", system_prompt="p1", is_builtin=True),
        )
        await tmp_sqlite_backend.create_preset(
            PresetCreate(name="内置2", system_prompt="p2", is_builtin=True),
        )
        builtins = await tmp_sqlite_backend.get_builtin_presets()
        assert len(builtins) == 2

    async def test_get_user_presets(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="m"))
        await tmp_sqlite_backend.create_preset(
            PresetCreate(user_id=user.id, name="自定义", system_prompt="cp"),
        )
        presets = await tmp_sqlite_backend.get_user_presets(user.id)
        assert len(presets) == 1
        assert presets[0].name == "自定义"

    async def test_update_and_delete_preset(self, tmp_sqlite_backend: SQLiteBackend):
        p = await tmp_sqlite_backend.create_preset(
            PresetCreate(name="旧名", system_prompt="sp"),
        )
        p.name = "新名"
        updated = await tmp_sqlite_backend.update_preset(p)
        assert updated.name == "新名"

        await tmp_sqlite_backend.delete_preset(p.id)
        assert await tmp_sqlite_backend.get_preset(p.id) is None


# =========================================================================
# UserConfig CRUD
# =========================================================================


class TestUserConfigStorage:
    """用户配置存储测试"""

    async def test_upsert_and_get(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="n"))
        cfg = await tmp_sqlite_backend.upsert_user_config(
            UserConfigCreate(user_id=user.id, key="theme", value="dark"),
        )
        assert cfg.key == "theme"
        assert cfg.value == "dark"

        fetched = await tmp_sqlite_backend.get_user_config(user.id, "theme")
        assert fetched is not None
        assert fetched.value == "dark"

    async def test_upsert_updates_existing(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="o"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=user.id, key="lang", value="zh"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=user.id, key="lang", value="en"))
        fetched = await tmp_sqlite_backend.get_user_config(user.id, "lang")
        assert fetched is not None
        assert fetched.value == "en"

    async def test_get_user_configs(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="p"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=user.id, key="a", value="1"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=user.id, key="b", value="2"))
        configs = await tmp_sqlite_backend.get_user_configs(user.id)
        assert len(configs) == 2

    async def test_delete_user_config(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(UserCreate(username="q"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=user.id, key="x", value="y"))
        await tmp_sqlite_backend.delete_user_config(user.id, "x")
        assert await tmp_sqlite_backend.get_user_config(user.id, "x") is None

    async def test_user_config_isolation(self, tmp_sqlite_backend: SQLiteBackend):
        u1 = await tmp_sqlite_backend.create_user(UserCreate(username="r"))
        u2 = await tmp_sqlite_backend.create_user(UserCreate(username="s"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=u1.id, key="k", value="v1"))
        await tmp_sqlite_backend.upsert_user_config(UserConfigCreate(user_id=u2.id, key="k", value="v2"))
        assert (await tmp_sqlite_backend.get_user_config(u1.id, "k")).value == "v1"
        assert (await tmp_sqlite_backend.get_user_config(u2.id, "k")).value == "v2"


# =====================================================================
# init_db —— 自动创建父目录
# =====================================================================


class TestInitDb:
    """init_db 健壮性"""

    async def test_init_db_creates_parent_directory(self, tmp_path: Path):
        """深层不存在的路径应能自动创建父目录"""
        db_path = tmp_path / "a" / "b" / "c" / "test.db"
        assert not db_path.parent.exists()
        backend = SQLiteBackend(path=str(db_path))
        await backend.init_db()
        assert db_path.parent.exists()
        assert db_path.exists()
        await backend.close()
