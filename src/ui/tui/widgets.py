"""
TUI 复用组件 —— widgets

【What】
共享的 rich Console、prompt_toolkit PromptSession、颜色和样式常量。

【Why】
- 统一 Console 实例，避免各处重复创建
- PromptSession 带历史记录和命令补全，替代裸 input()
"""

from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.shortcuts import PromptSession
from rich.console import Console

console = Console()

_COMMANDS = ["chat", "sessions", "presets", "search", "export", "compare", "switch", "exit"]
_command_completer = WordCompleter(_COMMANDS, ignore_case=True)
_cmd_session: PromptSession[str] | None = None
_input_session: PromptSession[str] | None = None


def _get_cmd_session() -> PromptSession[str]:
    global _cmd_session
    if _cmd_session is None:
        _cmd_session = PromptSession(completer=_command_completer, history=FileHistory(".cmd_history"))
    return _cmd_session


def _get_input_session() -> PromptSession[str]:
    global _input_session
    if _input_session is None:
        _input_session = PromptSession()
    return _input_session


async def get_command_prompt() -> str:
    """显示命令提示符并返回用户输入的命令名"""
    return (await _get_cmd_session().prompt_async("> ")).strip().lower()


async def get_input(prompt_text: str = "") -> str:
    """简单文本输入（异步）"""
    return (await _get_input_session().prompt_async(prompt_text)).strip()


async def get_input_with_default(prompt_text: str, default: str) -> str:
    """带默认值的文本输入（异步）"""
    val = await _get_input_session().prompt_async(prompt_text)
    return val.strip() or default
