"""
会话生命周期管理 —— SessionManager

【What】
管理会话的创建、加载、列表、重命名、删除、自动保存、标题自动生成及搜索。

【覆盖需求】
C1(新建会话)  C2(加载历史会话)  C3(会话列表)  C4(重命名)
C5(删除会话)  C6(自动保存)  C7(标题自动生成)  E1(对话搜索)  E2(Token 统计)  B4(用户隔离)

【Why】
- SessionManager 是 core/ 层对外暴露的核心组件之一，供 chat_engine 和 TUI 调用
- 所有方法都基于当前用户 ID 过滤数据（B4 用户隔离）

【Where】
- chat_engine 在对话过程中调用 add_user_message / add_ai_message
- TUI 各视图调用 list_sessions / rename_session / delete_session
- TUI 调用 create_session 发起新对话
"""

import logging
from typing import Optional

from src.models.schemas import Message, MessageCreate, Session, SessionCreate
from src.storage.base import StorageBackend

_LOGGER = logging.getLogger(__name__)


class SessionManager:
    """会话生命周期管理

    状态说明:
        _current_session: 当前活跃会话，为 None 表示不在会话中
        _title_generated: 内存缓存标记，避免每次 add_user_message 查库
                          - create_session 时设为 False
                          - load_session 时查一次库初始化
                          - 触发 C7 自动生成后设为 True
                          - rename_session 后设为 True（用户已手动命名）
    """

    def __init__(self, backend: StorageBackend, user_id: int):
        self._backend = backend
        self._user_id = user_id
        self._current_session: Optional[Session] = None
        self._title_generated: bool = False

    # ==================================================================
    # 内部辅助
    # ==================================================================

    def _assert_session_owner(self, session: Session) -> None:
        """确保会话属于当前用户，否则抛出 ValueError"""
        if session.user_id != self._user_id:
            raise ValueError(f"会话 {session.id} 不属于当前用户")

    def _assert_in_session(self) -> None:
        """确保当前存在活跃会话"""
        if self._current_session is None:
            raise RuntimeError("没有当前会话，请先调用 create_session 或 load_session")

    # ==================================================================
    # C1 — 新建会话
    # ==================================================================

    async def create_session(
        self,
        model_name: str,
        preset_id: Optional[int] = None,
    ) -> Session:
        """创建新会话并设为当前会话

        Args:
            model_name: 使用的模型名称（A5 支持中途切换）
            preset_id: 关联的预设 ID，None 表示不使用预设

        Returns:
            完整 Session 对象（id 由存储层自动生成）
        """
        session = await self._backend.create_session(
            SessionCreate(
                user_id=self._user_id,
                model_name=model_name,
                preset_id=preset_id,
            ),
        )
        self._current_session = session
        self._title_generated = False
        _LOGGER.info(
            "Session created",
            extra={"session_id": session.id, "user_id": self._user_id, "model_name": model_name},
        )
        return session

    # ==================================================================
    # C2 — 加载历史会话
    # ==================================================================

    async def load_session(self, session_id: int) -> Session:
        """加载指定会话并设为当前会话

        加载时检查是否已有 human 消息，初始化 _title_generated 标记。
        后续 add_user_message 不再重复查库（C7 优化）。

        Args:
            session_id: 目标会话 ID

        Returns:
            Session 对象

        Raises:
            ValueError: 会话不存在或不属于当前用户
        """
        session = await self._backend.get_session(session_id)
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")
        self._assert_session_owner(session)

        self._current_session = session
        # 查一次库判断标题是否已生成，后续不再重复查
        messages = await self._backend.get_messages_by_session(session_id)
        self._title_generated = any(m.role == "human" for m in messages)
        return session

    # ==================================================================
    # C3 — 会话列表
    # ==================================================================

    async def list_sessions(self) -> list[Session]:
        """返回当前用户的所有会话（按最后更新时间倒序）"""
        return await self._backend.get_sessions_by_user(self._user_id)

    # ==================================================================
    # C4 — 重命名
    # ==================================================================

    async def update_model(self, model_name: str) -> Session:
        """切换当前会话的模型并持久化

        A5: 保留历史上下文，仅更换 LLM 实例。
        重新 load_session 后 model_name 仍为切换后的值。
        """
        self._assert_in_session()
        assert self._current_session is not None

        self._current_session.model_name = model_name
        updated = await self._backend.update_session(self._current_session)
        self._current_session.model_name = updated.model_name
        return updated

    async def rename_session(self, session_id: int, new_title: str) -> Session:
        """修改会话标题

        重命名后标记 _title_generated = True，防止后续 C7 覆盖用户手动设置。
        """
        session = await self._backend.get_session(session_id)
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")
        self._assert_session_owner(session)

        session.title = new_title
        updated = await self._backend.update_session(session)

        # 同步更新内存缓存
        if self._current_session is not None and self._current_session.id == session_id:
            self._current_session.title = updated.title
            self._title_generated = True  # 用户已手动命名，不再自动生成
        return updated

    # ==================================================================
    # C5 — 删除会话
    # ==================================================================

    async def delete_session(self, session_id: int) -> None:
        """删除指定会话及其所有消息

        Raises:
            ValueError: 会话不存在或不属于当前用户
        """
        session = await self._backend.get_session(session_id)
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")
        self._assert_session_owner(session)

        await self._backend.delete_session(session_id)

        # 如果删除的是当前会话，清空缓存
        if self._current_session is not None and self._current_session.id == session_id:
            self._current_session = None
            self._title_generated = False

        _LOGGER.info("Session deleted", extra={"session_id": session_id, "user_id": self._user_id})

    # ==================================================================
    # C6 — 自动保存 + C7 — 标题自动生成 + E2 — Token 累计
    # ==================================================================

    async def add_user_message(
        self,
        content: str,
        prompt_tokens: int = 0,
    ) -> Message:
        """添加用户消息

        首次 human 消息自动触发 C7 标题生成（取前 30 字符）。
        每次写入后立即持久化（C6 自动保存）。

        Args:
            content: 消息内容
            prompt_tokens: 本轮消耗的 prompt tokens

        Returns:
            已持久化的 Message 对象
        """
        self._assert_in_session()
        assert self._current_session is not None

        # C7: 首条 human 消息自动生成标题
        if not self._title_generated:
            title = content.strip()[:30] if content.strip() else "未命名会话"
            self._current_session.title = title
            self._title_generated = True

        msg = await self._backend.create_message(
            MessageCreate(
                session_id=self._current_session.id,
                role="human",
                content=content,
                prompt_tokens=prompt_tokens,
            ),
        )

        # E2: 累计 token 并持久化（C6 自动保存）
        self._current_session.total_prompt_tokens += prompt_tokens
        await self._backend.update_session(self._current_session)

        return msg

    async def add_ai_message(
        self,
        content: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> Message:
        """添加 AI 回复消息

        prompt_tokens 计入本轮请求的输入 token（含历史上下文），
        completion_tokens 计入输出 token。

        Args:
            content: AI 回复内容
            prompt_tokens: 本轮请求消耗的 prompt tokens
            completion_tokens: 本轮输出消耗的 completion tokens
        """
        self._assert_in_session()
        assert self._current_session is not None

        msg = await self._backend.create_message(
            MessageCreate(
                session_id=self._current_session.id,
                role="ai",
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            ),
        )

        # E2: 累计 token 并持久化（C6 自动保存）
        self._current_session.total_prompt_tokens += prompt_tokens
        self._current_session.total_completion_tokens += completion_tokens
        await self._backend.update_session(self._current_session)

        return msg

    # ==================================================================
    # 属性访问
    # ==================================================================

    @property
    def current_session(self) -> Optional[Session]:
        """当前活跃会话，None 表示未进入会话"""
        return self._current_session

    @property
    def current_token_usage(self) -> tuple[int, int]:
        """返回 (累计 prompt_tokens, 累计 completion_tokens)"""
        if self._current_session is None:
            return (0, 0)
        return (
            self._current_session.total_prompt_tokens,
            self._current_session.total_completion_tokens,
        )

    async def search_messages(self, keyword: str) -> list[tuple[Session, list[Message]]]:
        """E1: 在当前用户所有会话中按关键词搜索消息

        Args:
            keyword: 搜索关键词（子串匹配）

        Returns:
            (会话, 匹配消息列表) 对，按会话 ID 分组
        """
        return await self._backend.search_messages(self._user_id, keyword)

    async def get_messages(self) -> list[Message]:
        """获取当前会话的全部历史消息（按创建时间正序）"""
        self._assert_in_session()
        assert self._current_session is not None
        return await self._backend.get_messages_by_session(self._current_session.id)
