"""
用户管理单元测试 —— test_user_manager

【覆盖需求】
B1(创建用户)  B2(获取用户)  B3(删除用户)  B4(用户隔离)
"""

import pytest

from src.core.user_manager import UserManager
from src.storage.sqlite_backend import SQLiteBackend


@pytest.fixture
async def mgr(tmp_sqlite_backend: SQLiteBackend) -> UserManager:
    """返回一个绑定临时后端的 UserManager 实例"""
    return UserManager(backend=tmp_sqlite_backend)


# =====================================================================
# B1 — 创建用户
# =====================================================================


class TestCreateUser:
    """B1 创建用户"""

    async def test_create_user_success(self, mgr: UserManager):
        user = await mgr.create_user(username="alice")
        assert user.id == 1
        assert user.username == "alice"
        assert user.default_model is None
        assert user.default_preset_id is None

    async def test_create_user_with_preferences(self, mgr: UserManager):
        user = await mgr.create_user(
            username="bob",
            default_model="gpt-4o",
        )
        assert user.default_model == "gpt-4o"
        assert user.default_preset_id is None

    async def test_create_user_duplicate_username_raises(self, mgr: UserManager):
        await mgr.create_user(username="alice")
        with pytest.raises(ValueError, match="已存在"):
            await mgr.create_user(username="alice")

    async def test_create_user_invalid_username_raises(self, mgr: UserManager):
        with pytest.raises(ValueError, match="仅允许"):
            await mgr.create_user(username="user@name")
        with pytest.raises(ValueError, match="仅允许"):
            await mgr.create_user(username="")
        with pytest.raises(ValueError, match="仅允许"):
            await mgr.create_user(username="user name")


# =====================================================================
# B2 — 获取用户
# =====================================================================


class TestGetUser:
    """B2 获取用户"""

    async def test_get_user_by_id(self, mgr: UserManager):
        created = await mgr.create_user(username="alice")
        fetched = await mgr.get_user(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.username == "alice"

    async def test_get_user_by_username(self, mgr: UserManager):
        await mgr.create_user(username="alice")
        fetched = await mgr.get_user_by_username("alice")
        assert fetched is not None
        assert fetched.username == "alice"

    async def test_get_user_nonexistent_returns_none(self, mgr: UserManager):
        assert await mgr.get_user(999) is None
        assert await mgr.get_user_by_username("nonexistent") is None


# =====================================================================
# update_user — 更新用户偏好
# =====================================================================


class TestUpdateUser:
    """update_user 更新用户偏好"""

    async def test_update_user_preferences(self, mgr: UserManager):
        user = await mgr.create_user(username="alice")
        user.default_model = "gpt-4o"
        updated = await mgr.update_user(user)
        assert updated.default_model == "gpt-4o"
        # 重新查询验证持久化
        fetched = await mgr.get_user(user.id)
        assert fetched is not None
        assert fetched.default_model == "gpt-4o"

    async def test_update_user_duplicate_username_raises(self, mgr: UserManager):
        await mgr.create_user(username="alice")
        bob = await mgr.create_user(username="bob")
        bob.username = "alice"
        with pytest.raises(ValueError, match="已存在"):
            await mgr.update_user(bob)


# =====================================================================
# B3 — 删除用户
# =====================================================================


class TestDeleteUser:
    """B3 删除用户"""

    async def test_delete_user_cascades(self, mgr: UserManager, tmp_sqlite_backend: SQLiteBackend):
        user = await mgr.create_user(username="alice")
        await mgr.delete_user(user.id)
        # 用户已不存在
        assert await mgr.get_user(user.id) is None
        # 确认 storage 层也无法查到
        assert await tmp_sqlite_backend.get_user(user.id) is None

    async def test_delete_user_nonexistent_raises(self, mgr: UserManager):
        with pytest.raises(ValueError, match="不存在"):
            await mgr.delete_user(999)
