"""
UI 协议接口 —— UIProtocol

【What】
定义 TUI / WebUI 必须实现的操作接口，与核心业务层解耦。

【Why】
- core/ 层不依赖 ui/ 层（AGENTS.md 核心约束）
- TUI 和 WebUI 各自实现此协议，切换 UI 时不改动 core/
- 使用 typing.Protocol 而非 ABC，实现方无需继承，结构匹配即可

【Where】
- ui/tui/app.py 隐式实现此协议
- ui/web/ 后续实现时参考此协议
"""

from typing import AsyncIterator, Optional, Protocol, runtime_checkable

from src.models.schemas import Message, Preset, Session, User


@runtime_checkable
class UIProtocol(Protocol):
    """UI 必须实现的接口协议

    TUIApp 实现时直接持有 UserManager / SessionManager / PresetManager /
    ChatEngine / ConfigManager 五个实例，各方法委托到对应 Manager。
    """

    # ==================================================================
    # User —— 用户管理
    # ==================================================================

    async def create_user(
        self,
        username: str,
        default_model: Optional[str] = None,
        default_preset_id: Optional[int] = None,
    ) -> User:
        """B1: 创建新用户"""
        ...

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """B2: 按用户名查找（切换用户前置）"""
        ...

    async def switch_user(self, username: str) -> None:
        """B2: 切换当前用户

        实现方（TUIApp）必须原子性重建 SessionManager 和 ChatEngine：
          - 新 SessionManager(backend, new_user.id)
          - 新 ChatEngine(new_session_mgr, config)
        只切换一个会导致用户身份不一致。
        """
        ...

    async def delete_user(self, user_id: int) -> None:
        """B3: 删除用户"""
        ...

    # ==================================================================
    # Session —— 会话管理
    # ==================================================================

    async def create_session(
        self,
        model_name: str,
        preset_id: Optional[int] = None,
    ) -> Session:
        """C1: 新建会话"""
        ...

    async def load_session(self, session_id: int) -> Session:
        """C2: 加载历史会话"""
        ...

    async def list_sessions(self) -> list[Session]:
        """C3: 会话列表"""
        ...

    async def rename_session(self, session_id: int, new_title: str) -> Session:
        """C4: 重命名会话"""
        ...

    async def delete_session(self, session_id: int) -> None:
        """C5: 删除会话"""
        ...

    @property
    def current_session(self) -> Optional[Session]:
        """当前活跃会话"""
        ...

    async def get_messages(self) -> list[Message]:
        """获取当前会话的历史消息"""
        ...

    async def search_messages(self, keyword: str) -> list[tuple[Session, list[Message]]]:
        """E1: 在当前用户所有会话中按关键词搜索消息"""
        ...

    async def export_session(self, session_id: int) -> str:
        """F1/F2: 将会话导出为 Markdown 文件，返回文件路径"""
        ...

    async def switch_model(self, model_name: str) -> None:
        """A5: 切换当前会话的模型"""
        ...

    # ==================================================================
    # Chat —— 对话
    # ==================================================================

    async def chat(self, content: str) -> AsyncIterator[str]:
        """A1/A2: 执行一轮对话，逐 token 产出 LLM 回复"""
        ...

    # ==================================================================
    # Preset —— 预设管理
    # ==================================================================

    async def list_builtin_presets(self) -> list[Preset]:
        """D1: 系统内置预设列表（只读）"""
        ...

    async def list_user_presets(self) -> list[Preset]:
        """D2/D4: 当前用户的预设列表"""
        ...

    async def create_preset(
        self,
        name: str,
        system_prompt: str,
        description: Optional[str] = None,
    ) -> Preset:
        """D2: 创建自定义预设"""
        ...

    async def update_preset(
        self,
        preset_id: int,
        name: str,
        description: Optional[str],
        system_prompt: str,
    ) -> Preset:
        """D2: 更新预设"""
        ...

    async def delete_preset(self, preset_id: int) -> None:
        """D2: 删除预设"""
        ...

    # ==================================================================
    # Token —— Token 用量统计
    # ==================================================================

    @property
    def current_token_usage(self) -> tuple[int, int]:
        """E2: 当前会话的 (prompt_tokens, completion_tokens)"""
        ...
