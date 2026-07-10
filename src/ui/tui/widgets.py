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
from prompt_toolkit.shortcuts import prompt as pt_prompt
from rich.console import Console

console = Console()

_COMMANDS = ["chat", "sessions", "presets", "search", "export", "compare", "switch", "exit"]
_command_completer = WordCompleter(_COMMANDS, ignore_case=True)


def get_command_prompt() -> str:
    """显示命令提示符并返回用户输入的命令名"""
    return pt_prompt("> ", completer=_command_completer, history=FileHistory(".cmd_history")).strip().lower()


def get_input(prompt_text: str = "") -> str:
    """简单文本输入（不用补全和历史）"""
    return pt_prompt(prompt_text).strip()


def get_input_with_default(prompt_text: str, default: str) -> str:
    """带默认值的文本输入"""
    val = pt_prompt(prompt_text).strip()
    return val or default
