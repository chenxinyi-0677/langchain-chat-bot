"""
用户管理 —— UserManager

【What】
管理用户的创建、查询、更新和删除。

【覆盖需求】
B1(创建用户)  B2(切换用户前置)  B3(删除用户)  B4(用户隔离)

【Why】
- UserManager 是 core/ 层的用户注册中心，不绑定"当前用户"概念
- B4 用户隔离在其他 Manager（如 SessionManager）中通过 user_id 过滤天然实现
- "当前用户"概念归属应用层（TUI app.py），由应用层在切换用户时重建
  绑定新 user_id 的 SessionManager

【Where】
- TUI 调用 create_user / get_user_by_username 实现注册 B1 和登录 B2
- delete_user 由 TUI 菜单触发，二次确认在 UI 层完成
- update_user 由用户设置功能调用，修改 default_model / default_preset_id
"""

import logging
import re
from typing import Optional

from src.models.schemas import User, UserCreate
from src.storage.base import StorageBackend

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
_LOGGER = logging.getLogger(__name__)


class UserManager:
    """用户管理

    【状态说明】
    不缓存任何用户状态，每次操作直通存储层。
    """

    def __init__(self, backend: StorageBackend):
        self._backend = backend

    # ==================================================================
    # B1 — 创建用户
    # ==================================================================

    async def create_user(
        self,
        username: str,
        default_model: Optional[str] = None,
        default_preset_id: Optional[int] = None,
    ) -> User:
        """创建新用户

        Args:
            username: 用户名，仅允许字母/数字/下划线/连字符，1-50 字符
            default_model: 默认模型名称（可选）
            default_preset_id: 默认预设 ID（可选）

        Returns:
            完整 User 对象（id 由存储层自动生成）

        Raises:
            ValueError: 用户名格式不合法或已存在
        """
        if not _USERNAME_RE.match(username):
            raise ValueError(
                "用户名仅允许字母、数字、下划线和连字符"
            )
        user = await self._backend.create_user(
            UserCreate(
                username=username,
                default_model=default_model,
                default_preset_id=default_preset_id,
            ),
        )
        _LOGGER.info("User created", extra={"username": user.username, "user_id": user.id})
        return user

    # ==================================================================
    # B2 — 获取用户（切换用户的前置条件）
    # ==================================================================

    async def get_user(self, user_id: int) -> Optional[User]:
        """按 ID 查询用户"""
        return await self._backend.get_user(user_id)

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """按用户名查询（登录 / 切换用）"""
        return await self._backend.get_user_by_username(username)

    # ==================================================================
    # update_user — 更新用户偏好
    # ==================================================================

    async def update_user(self, user: User) -> User:
        """更新用户偏好

        Args:
            user: 包含更新后字段的完整 User 对象

        Returns:
            更新后的完整 User 对象

        Raises:
            ValueError: 更新后的用户名与已有用户冲突
        """
        return await self._backend.update_user(user)

    # ==================================================================
    # B3 — 删除用户
    # ==================================================================

    async def delete_user(self, user_id: int) -> None:
        """删除用户（级联删除关联会话/消息/预设/配置）

        Args:
            user_id: 目标用户 ID

        Raises:
            ValueError: 用户不存在
        """
        user = await self._backend.get_user(user_id)
        if user is None:
            _LOGGER.warning("Delete failed: user not found", extra={"user_id": user_id})
            raise ValueError(f"用户 {user_id} 不存在")
        await self._backend.delete_user(user_id)
        _LOGGER.info("User deleted", extra={"user_id": user_id, "username": user.username})
