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


class TUIApp:
    """TUI 主应用"""

    def __init__(self, backend: StorageBackend, config: AppConfig):
        self._backend = backend
        self._config = config

        # 全局唯一（不绑定用户）
        self._user_mgr = UserManager(backend=backend)

        # 绑定当前用户，switch_user 时重建
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
        """启动 TUI 主循环"""
        try:
            await self._login_flow()
            await self._main_loop()
        finally:
            await self._backend.close()

    # ==================================================================
    # 登录流程
    # ==================================================================

    async def _login_flow(self) -> None:
        """首次启动或无用户时走创建流程"""
        users = await self._backend.list_users()
        if not users:
            username = input("欢迎！请输入用户名创建账号: ").strip()
            while not username:
                username = input("用户名不能为空: ").strip()
            user = await self._user_mgr.create_user(username=username)
            print(f"用户 '{user.username}' 创建成功！")
        else:
            print("已有用户:")
            for i, u in enumerate(users, 1):
                print(f"  {i}. {u.username}")
            choice = input("请输入用户名或编号: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(users):
                    user = users[idx]
                else:
                    user = users[0]
                    print(f"编号无效，默认选中 '{user.username}'")
            else:
                matched = [u for u in users if u.username == choice]
                if matched:
                    user = matched[0]
                else:
                    print(f"用户 '{choice}' 不存在，创建新用户")
                    user = await self._user_mgr.create_user(username=choice)
        await self._switch_to_user(user)

    async def _switch_to_user(self, user: User) -> None:
        """绑定当前用户（原子性重建三个 Manager）"""
        self._current_user = user
        self._session_mgr = SessionManager(backend=self._backend, user_id=user.id)
        self._preset_mgr = PresetManager(backend=self._backend, user_id=user.id)
        self._chat_engine = ChatEngine(session_mgr=self._session_mgr, config=self._config)
        self._exporter = Exporter(backend=self._backend, user_id=user.id, username=user.username)

    # ==================================================================
    # 主循环
    # ==================================================================

    async def _main_loop(self) -> None:
        """命令路由骨架"""
        print(f"\n当前用户: {self._current_user.username}")
        while True:
            cmd = input("\n> ").strip().lower()
            if cmd == "exit":
                print("再见！")
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
                print("可用命令: chat  sessions  presets  search  export  compare  switch  exit")

    # ==================================================================
    # chat 命令
    # ==================================================================

    async def _cmd_chat(self) -> None:
        """进入对话模式

        前置条件检查：如果无当前会话，走创建会话流程：
          1. 输入模型名（可回车使用默认值）
          2. 选择预设（可回车跳过）
          3. 调用 create_session 后进入对话循环
        """
        assert self._session_mgr is not None

        if self._session_mgr.current_session is None:
            model_name = input(f"模型名（默认 {self._config.env.model_name}）: ").strip()
            if not model_name:
                model_name = self._config.env.model_name

            presets = await self._preset_mgr.list_user_presets()
            builtins = await self._preset_mgr.list_builtin_presets()
            all_presets = builtins + presets
            preset_id = None
            if all_presets:
                print("可用预设:")
                print("  0. 不使用预设")
                for i, p in enumerate(all_presets, 1):
                    marker = " [内置]" if p.is_builtin else ""
                    print(f"  {i}. {p.name}{marker}")
                choice = input("选择预设编号（回车 = 不使用）: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(all_presets):
                    preset_id = all_presets[int(choice) - 1].id

            await self._session_mgr.create_session(
                model_name=model_name,
                preset_id=preset_id,
            )
            print(f"会话已创建（{model_name}）")

        print("对话模式（输入空行返回主菜单）:")
        while True:
            content = input("\n你: ").strip()
            if not content:
                break
            print("AI: ", end="", flush=True)
            async for token in self._chat_engine.chat(content):
                print(token, end="", flush=True)
            print()

    # ==================================================================
    # sessions 命令（骨架）
    # ==================================================================

    async def _cmd_sessions(self) -> None:
        """会话管理 —— 后续用 rich 表格完善"""
        assert self._session_mgr is not None
        sessions = await self._session_mgr.list_sessions()
        if not sessions:
            print("暂无会话")
            return
        print("会话列表:")
        for s in sessions:
            title = s.title or "未命名"
            print(f"  [{s.id}] {title} ({s.model_name})")
        print("（管理功能待实现）")

    # ==================================================================
    # presets 命令（骨架）
    # ==================================================================

    async def _cmd_presets(self) -> None:
        """预设管理 —— 后续用 rich 表格完善"""
        assert self._preset_mgr is not None
        builtins = await self._preset_mgr.list_builtin_presets()
        user_presets = await self._preset_mgr.list_user_presets()
        print("内置预设:")
        for p in builtins:
            print(f"  [{p.id}] {p.name}")
        print("我的预设:")
        if user_presets:
            for p in user_presets:
                print(f"  [{p.id}] {p.name}")
        else:
            print("  （无）")
        print("（管理功能待实现）")

    # ==================================================================
    # search 命令 —— E1 对话搜索
    # ==================================================================

    async def _cmd_search(self) -> None:
        """按关键词搜索当前用户所有会话中的消息"""
        assert self._session_mgr is not None
        keyword = input("搜索关键词: ").strip()
        if not keyword:
            return
        results = await self._session_mgr.search_messages(keyword)
        if not results:
            print("未找到匹配的消息")
            return
        for session, messages in results:
            title = session.title or "未命名会话"
            print(f"\n┌─ [{session.id}] {title}")
            for msg in messages:
                role = "你" if msg.role == "human" else "AI"
                content = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                print(f"│ {role}: {content}")
            print(f"└─ {len(messages)} 条匹配")

    # ==================================================================
    # export 命令 —— F1/F2 对话导出
    # ==================================================================

    async def _cmd_export(self) -> None:
        """将会话导出为 Markdown 文件"""
        assert self._session_mgr is not None
        assert self._exporter is not None
        session_id_str = input("要导出的会话 ID: ").strip()
        if not session_id_str or not session_id_str.isdigit():
            print("无效的会话 ID")
            return
        session_id = int(session_id_str)
        try:
            path = await self._exporter.export(session_id)
            print(f"导出成功: {path}")
        except ValueError as e:
            print(e)

    # ==================================================================
    # compare 命令 —— H2 多模型并行对比
    # ==================================================================

    async def _cmd_compare(self) -> None:
        """将同一 prompt 同时发送给多个模型，对比输出"""
        prompt = input("对比提示词: ").strip()
        if not prompt:
            return
        raw = input("模型名（逗号分隔，如 gpt-4o,deepseek-chat）: ").strip()
        if not raw:
            return
        model_names = [m.strip() for m in raw.split(",") if m.strip()]
        if not model_names:
            print("至少需要一个模型")
            return

        print(f"\n正在并发调用 {len(model_names)} 个模型，请稍候...\n")
        results = await self._comparator.compare(prompt, model_names)

        for result in results:
            sep = "=" * 60
            print(sep)
            print(f"模型: {result.model_name}")
            print(sep)
            if result.error:
                print(f"[错误] {result.error}")
            else:
                print(result.response)
                print(f"\n--- prompt_tokens={result.prompt_tokens}, completion_tokens={result.completion_tokens}")

    # ==================================================================
    # switch 命令
    # ==================================================================

    async def _cmd_switch_user(self) -> None:
        """切换用户（原子性重建 Manager）"""
        assert self._user_mgr is not None
        username = input("目标用户名: ").strip()
        if not username:
            return
        user = await self._user_mgr.get_user_by_username(username)
        if user is None:
            confirm = input(f"用户 '{username}' 不存在，是否创建？(y/n): ").strip().lower()
            if confirm != "y":
                return
            user = await self._user_mgr.create_user(username=username)
        await self._switch_to_user(user)
        print(f"已切换至 '{user.username}'")
