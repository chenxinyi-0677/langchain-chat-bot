"""
对话视图 —— chat_view

【What】
用 rich 渲染对话界面，AI 回复部分使用 Live 逐 token 刷新，
保留 A2 流式输出的实时感。

【Why】
- 用户消息瞬间渲染（蓝色 Panel）
- AI 回复逐 token 刷新（绿色 Panel + Live）
"""

from typing import AsyncIterator

from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from src.ui.tui.widgets import console


def show_user_message(content: str) -> None:
    """显示用户消息（蓝色 Panel，瞬间渲染）"""
    panel = Panel(Text(content), title="你", border_style="blue", title_align="left")
    console.print(panel)


async def show_ai_stream(stream: AsyncIterator[str]) -> None:
    """流式显示 AI 回复，逐 token 刷新 Panel 内容"""
    ai_text = Text()
    panel = Panel(ai_text, title="AI", border_style="green", title_align="left")
    with Live(panel, console=console, refresh_per_second=15, vertical_overflow="visible") as live:
        async for token in stream:
            ai_text.append(token)
            live.update(panel)
