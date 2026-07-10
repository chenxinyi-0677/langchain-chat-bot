"""
TUI 主应用 —— TUIApp

【What】
基于 rich + prompt_toolkit 的命令行交互界面。
隐式实现 src/interface/ui_protocol.py 中的 UIProtocol。

【Why】
- 直接持有各 Manager 实例，通过委托满足协议要求
- switch_user 时原子性重建 SessionManager / PresetManager / ChatEngine

【Where】
- main.py 启动后调用 TUIApp.run() 进入主循环
"""

from typing import Optional

from src.core.chat_engine import ChatEngine
from src.core.comparator import Comparator
from src.core.config_manager import AppConfig
from src.core.exporter import Exporter
from src.core.preset_manager import PresetManager
from src.core.session_manager import SessionManager
from src.core.user_manager import UserManager
from src.models.schemas import User
from src.storage.base import StorageBackend
from src.ui.tui.chat_view import show_ai_stream, show_user_message
from src.ui.tui.menu_view import (
    show_compare_results,
    show_error,
    show_help,
    show_message,
    show_presets,
    show_search_results,
    show_sessions,
    show_success,
)
from src.ui.tui.widgets import get_command_prompt, get_input, get_input_with_default


class TUIApp:
    """TUI 主应用"""

    def __init__(self, backend: StorageBackend, config: AppConfig):
        self._backend = backend
        self._config = config

        self._user_mgr = UserManager(backend=backend)

        self._current_user: Optional[User] = None
        self._session_mgr: Optional[SessionManager] = None
        self._preset_mgr: Optional[PresetManager] = None
        self._chat_engine: Optional[ChatEngine] = None
        self._exporter: Optional[Exporter] = None
        self._comparator = Comparator(config=config)

    # ==================================================================
    # 入口
    # ==================================================================

    async def run(self) -> None:
        try:
            await self._login_flow()
            await self._main_loop()
        finally:
            await self._backend.close()

    # ==================================================================
    # 登录流程
    # ==================================================================

    async def _login_flow(self) -> None:
        users = await self._backend.list_users()
        if not users:
            username = get_input("欢迎！请输入用户名创建账号: ")
            while not username:
                username = get_input("用户名不能为空: ")
            user = await self._user_mgr.create_user(username=username)
            show_success(f"用户 '{user.username}' 创建成功！")
        else:
            show_message("已有用户:")
            for i, u in enumerate(users, 1):
                show_message(f"  {i}. {u.username}")
            choice = get_input("请输入用户名或编号: ")
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(users):
                    user = users[idx]
                else:
                    user = users[0]
                    show_error(f"编号无效，默认选中 '{user.username}'")
            else:
                matched = [u for u in users if u.username == choice]
                if matched:
                    user = matched[0]
                else:
                    show_message(f"用户 '{choice}' 不存在，创建新用户")
                    user = await self._user_mgr.create_user(username=choice)
        await self._switch_to_user(user)

    async def _switch_to_user(self, user: User) -> None:
        self._current_user = user
        self._session_mgr = SessionManager(backend=self._backend, user_id=user.id)
        self._preset_mgr = PresetManager(backend=self._backend, user_id=user.id)
        self._chat_engine = ChatEngine(session_mgr=self._session_mgr, config=self._config)
        self._exporter = Exporter(backend=self._backend, user_id=user.id, username=user.username)

    # ==================================================================
    # 主循环
    # ==================================================================

    async def _main_loop(self) -> None:
        show_success(f"当前用户: {self._current_user.username}")
        while True:
            cmd = get_command_prompt()
            if cmd == "exit":
                show_message("再见！")
                break
            elif cmd == "chat":
                await self._cmd_chat()
            elif cmd == "sessions":
                await self._cmd_sessions()
            elif cmd == "presets":
                await self._cmd_presets()
            elif cmd == "search":
                await self._cmd_search()
            elif cmd == "export":
                await self._cmd_export()
            elif cmd == "compare":
                await self._cmd_compare()
            elif cmd == "switch":
                await self._cmd_switch_user()
            else:
                show_help()

    # ==================================================================
    # chat 命令
    # ==================================================================

    async def _cmd_chat(self) -> None:
        assert self._session_mgr is not None

        if self._session_mgr.current_session is None:
            model_name = get_input_with_default(
                f"模型名（默认 {self._config.env.model_name}）: ",
                self._config.env.model_name,
            )

            presets = await self._preset_mgr.list_user_presets()
            builtins = await self._preset_mgr.list_builtin_presets()
            all_presets = builtins + presets
            preset_id = None
            if all_presets:
                show_message("可用预设:")
                show_message("  0. 不使用预设")
                for i, p in enumerate(all_presets, 1):
                    marker = " [内置]" if p.is_builtin else ""
                    show_message(f"  {i}. {p.name}{marker}")
                choice = get_input("选择预设编号（回车 = 不使用）: ")
                if choice.isdigit() and 1 <= int(choice) <= len(all_presets):
                    preset_id = all_presets[int(choice) - 1].id

            await self._session_mgr.create_session(
                model_name=model_name,
                preset_id=preset_id,
            )
            show_success(f"会话已创建（{model_name}）")

        show_message("对话模式（输入空行返回主菜单）:")
        while True:
            content = get_input("你: ")
            if not content:
                break
            show_user_message(content)
            await show_ai_stream(self._chat_engine.chat(content))

    # ==================================================================
    # sessions 命令
    # ==================================================================

    async def _cmd_sessions(self) -> None:
        assert self._session_mgr is not None
        sessions = await self._session_mgr.list_sessions()
        show_sessions(sessions)

    # ==================================================================
    # presets 命令
    # ==================================================================

    async def _cmd_presets(self) -> None:
        assert self._preset_mgr is not None
        builtins = await self._preset_mgr.list_builtin_presets()
        user_presets = await self._preset_mgr.list_user_presets()
        show_presets(builtins, user_presets)

    # ==================================================================
    # search 命令
    # ==================================================================

    async def _cmd_search(self) -> None:
        assert self._session_mgr is not None
        keyword = get_input("搜索关键词: ")
        if not keyword:
            return
        results = await self._session_mgr.search_messages(keyword)
        show_search_results(results)

    # ==================================================================
    # export 命令
    # ==================================================================

    async def _cmd_export(self) -> None:
        assert self._session_mgr is not None
        assert self._exporter is not None
        session_id_str = get_input("要导出的会话 ID: ")
        if not session_id_str or not session_id_str.isdigit():
            show_error("无效的会话 ID")
            return
        session_id = int(session_id_str)
        try:
            path = await self._exporter.export(session_id)
            show_success(f"导出成功: {path}")
        except ValueError as e:
            show_error(str(e))

    # ==================================================================
    # compare 命令
    # ==================================================================

    async def _cmd_compare(self) -> None:
        prompt = get_input("对比提示词: ")
        if not prompt:
            return
        raw = get_input("模型名（逗号分隔，如 gpt-4o,deepseek-chat）: ")
        if not raw:
            return
        model_names = [m.strip() for m in raw.split(",") if m.strip()]
        if not model_names:
            show_error("至少需要一个模型")
            return

        show_message(f"正在并发调用 {len(model_names)} 个模型，请稍候...")
        results = await self._comparator.compare(prompt, model_names)
        show_compare_results(results)

    # ==================================================================
    # switch 命令
    # ==================================================================

    async def _cmd_switch_user(self) -> None:
        assert self._user_mgr is not None
        username = get_input("目标用户名: ")
        if not username:
            return
        user = await self._user_mgr.get_user_by_username(username)
        if user is None:
            confirm = get_input(f"用户 '{username}' 不存在，是否创建？(y/n): ")
            if confirm.lower() != "y":
                return
            user = await self._user_mgr.create_user(username=username)
        await self._switch_to_user(user)
        show_success(f"已切换至 '{user.username}'")
