"""
菜单视图 —— menu_view

【What】
用 rich Table / Panel 渲染会话列表、预设列表、搜索结果、模型对比结果。

【Why】
- 统一的美化渲染入口，让 app.py _cmd_* 方法只需调用 view 函数
"""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.ui.tui.widgets import console


def show_help() -> None:
    """显示可用命令列表"""
    text = Text("chat  sessions  presets  search  export  compare  switch  exit")
    console.print(Panel(text, title="可用命令", border_style="cyan"))


def show_sessions(sessions: list) -> None:
    """将会话列表渲染为表格"""
    if not sessions:
        console.print("[yellow]暂无会话[/yellow]")
        return
    table = Table(title="会话列表", header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("标题")
    table.add_column("模型")
    table.add_column("Token", justify="right")
    for s in sessions:
        title = s.title or "未命名"
        tokens = f"{s.total_prompt_tokens + s.total_completion_tokens}"
        table.add_row(str(s.id), title, s.model_name, tokens)
    console.print(table)


def show_presets(builtins: list, user_presets: list) -> None:
    """将预设列表渲染为两个表格"""
    if builtins:
        bt = Table(title="内置预设", header_style="bold cyan")
        bt.add_column("ID", style="dim")
        bt.add_column("名称")
        for p in builtins:
            bt.add_row(str(p.id), p.name)
        console.print(bt)
    else:
        console.print("[yellow]暂无内置预设[/yellow]")

    if user_presets:
        ut = Table(title="我的预设", header_style="bold green")
        ut.add_column("ID", style="dim")
        ut.add_column("名称")
        ut.add_column("描述")
        for p in user_presets:
            desc = p.description or ""
            ut.add_row(str(p.id), p.name, desc)
        console.print(ut)
    else:
        console.print("[yellow]暂无自定义预设[/yellow]")


def show_search_results(results: list) -> None:
    """将搜索结果按会话分组渲染"""
    if not results:
        console.print("[yellow]未找到匹配的消息[/yellow]")
        return
    for session, messages in results:
        title = session.title or "未命名会话"
        lines = []
        for msg in messages:
            role = "你" if msg.role == "human" else "AI"
            content = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
            lines.append(f"{role}: {content}")
        panel = Panel("\n".join(lines), title=f"[{session.id}] {title} ({len(messages)} 条匹配)", border_style="cyan")
        console.print(panel)


def show_compare_results(results: list) -> None:
    """将多模型对比结果逐模型渲染"""
    for result in results:
        if result.error:
            content = Text(f"[错误] {result.error}", style="red")
        else:
            content = Text(result.response)
            stats = f"\n\nprompt_tokens={result.prompt_tokens}, completion_tokens={result.completion_tokens}"
            content.append(Text(stats, style="dim"))
        panel = Panel(content, title=result.model_name, border_style="magenta")
        console.print(panel)


def show_message(text: str, style: str = "") -> None:
    """简单文本输出"""
    if style:
        console.print(f"[{style}]{text}[/{style}]")
    else:
        console.print(text)


def show_error(text: str) -> None:
    """错误消息"""
    console.print(f"[bold red]{text}[/bold red]")


def show_success(text: str) -> None:
    """成功消息"""
    console.print(f"[bold green]{text}[/bold green]")
