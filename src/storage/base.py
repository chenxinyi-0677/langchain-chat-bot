"""
存储层抽象基类 —— StorageBackend

【What】
定义所有存储后端必须实现的统一异步 CRUD 接口。

【Why】
实现 4.1 节"可插拔存储后端"设计：业务层通过此接口调用持久化，
无需关心底层是 SQLite / MySQL / File。

【Where】
SQLiteBackend / MySQLBackend / FileBackend 继承此类实现各自逻辑。
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.models.schemas import (
    Message,
    MessageCreate,
    Preset,
    PresetCreate,
    Session,
    SessionCreate,
    User,
    UserConfig,
    UserConfigCreate,
    UserCreate,
)


class StorageBackend(ABC):
    """存储后端抽象基类"""

    # ------------------------------------------------------------------
    # 连接生命周期
    # ------------------------------------------------------------------

    @abstractmethod
    async def init_db(self) -> None:
        """初始化数据库：建表、建索引，启动时调用一次"""
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭连接 / 释放资源"""
        ...

    # ------------------------------------------------------------------
    # User —— 用户管理（B1, B2, B3, B4）
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_user(self, user: UserCreate) -> User:
        """创建用户，username 重复时应抛出 ValueError"""
        ...

    @abstractmethod
    async def get_user(self, user_id: int) -> Optional[User]:
        """按用户 ID 查询"""
        ...

    @abstractmethod
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """按用户名查询（登录 / 切换用）"""
        ...

    @abstractmethod
    async def update_user(self, user: User) -> User:
        """更新用户偏好，返回更新后的完整 User"""
        ...

    @abstractmethod
    async def delete_user(self, user_id: int) -> None:
        """删除用户（级联删除关联会话 / 消息 / 预设 / 配置）"""
        ...

    @abstractmethod
    async def list_users(self) -> list[User]:
        """列出所有用户"""
        ...

    # ------------------------------------------------------------------
    # Session —— 会话管理（C1~C7）
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_session(self, session: SessionCreate) -> Session:
        """新建会话，title 为 None 时自动兜底"""
        ...

    @abstractmethod
    async def get_session(self, session_id: int) -> Optional[Session]:
        """按会话 ID 查询"""
        ...

    @abstractmethod
    async def get_sessions_by_user(self, user_id: int) -> list[Session]:
        """查询某用户的所有会话（按更新时间倒序）"""
        ...

    @abstractmethod
    async def update_session(self, session: Session) -> Session:
        """更新会话（标题 / token 累计 / 模型切换）"""
        ...

    @abstractmethod
    async def delete_session(self, session_id: int) -> None:
        """删除会话（级联删除关联消息）"""
        ...

    # ------------------------------------------------------------------
    # Message —— 消息（A1, A2, C6, E1, E2, F1）
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_message(self, msg: MessageCreate) -> Message:
        """写入单条消息"""
        ...

    @abstractmethod
    async def get_messages_by_session(
        self,
        session_id: int,
    ) -> list[Message]:
        """查询某会话的全部历史消息（按创建时间正序）"""
        ...

    @abstractmethod
    async def search_messages(
        self,
        user_id: int,
        keyword: str,
    ) -> list[tuple[Session, list[Message]]]:
        """在用户所有会话中按关键词搜索消息，返回 (会话, 消息列表) 对"""
        ...

    # ------------------------------------------------------------------
    # Preset —— 预设 Prompt（D1~D4）
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_preset(self, preset: PresetCreate) -> Preset:
        """创建自定义预设"""
        ...

    @abstractmethod
    async def get_preset(self, preset_id: int) -> Optional[Preset]:
        """按预设 ID 查询"""
        ...

    @abstractmethod
    async def get_builtin_presets(self) -> list[Preset]:
        """获取所有系统内置预设（user_id IS NULL）"""
        ...

    @abstractmethod
    async def get_user_presets(self, user_id: int) -> list[Preset]:
        """获取某用户的自定义预设"""
        ...

    @abstractmethod
    async def update_preset(self, preset: Preset) -> Preset:
        """编辑预设"""
        ...

    @abstractmethod
    async def delete_preset(self, preset_id: int) -> None:
        """删除预设（内置不可删由业务层判断，存储层不关心）"""
        ...

    # ------------------------------------------------------------------
    # UserConfig —— 用户偏好键值对（B4）
    # ------------------------------------------------------------------

    @abstractmethod
    async def upsert_user_config(self, cfg: UserConfigCreate) -> UserConfig:
        """存在则更新，不存在则创建"""
        ...

    @abstractmethod
    async def get_user_config(
        self,
        user_id: int,
        key: str,
    ) -> Optional[UserConfig]:
        """查询单条配置"""
        ...

    @abstractmethod
    async def get_user_configs(self, user_id: int) -> list[UserConfig]:
        """列出某用户所有配置"""
        ...

    @abstractmethod
    async def delete_user_config(self, user_id: int, key: str) -> None:
        """删除单条配置"""
        ...
