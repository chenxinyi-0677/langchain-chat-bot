"""
对话导出 —— Exporter

【What】
将会话的完整对话记录导出为格式化的 Markdown 文件。

【覆盖需求】
F1(导出Markdown)  F2(写入 data/users/{username}/exports/)

【Why】
- Exporter 是 core/ 层独立模块，不耦合到 SessionManager
- 文件 I/O + Markdown 格式化 + 文件名清理集中管理，便于测试

【Where】
- TUI 在 export 命令中调用 Exporter.export(session_id)
- 输出目录 data/users/{username}/exports/ 由 .gitignore 排除
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from src.models.schemas import Message, Session
from src.storage.base import StorageBackend


class Exporter:
    """会话导出器

    通过 StorageBackend 读取会话和消息，格式化为 Markdown 后写入文件。
    数据库时间戳存储为 UTC，导出时转换为本地时区以便阅读。

    Args:
        backend: 存储后端（用于按 ID 获取会话和消息）
        user_id: 当前用户 ID（用于归属校验）
        username: 当前用户名（用于构造导出路径）
    """

    EXPORT_DIR_TEMPLATE = "data/users/{username}/exports"

    def __init__(self, backend: StorageBackend, user_id: int, username: str):
        self._backend = backend
        self._user_id = user_id
        self._username = username

    def _export_dir(self) -> Path:
        return Path(self.EXPORT_DIR_TEMPLATE.format(username=self._username))

    @staticmethod
    def _sanitize_title(title: str) -> str:
        """清理标题中文件系统不允许的字符

        Windows/Linux 通用的非法字符: \\ / : * ? \" < > |
        替换为下划线，避免 FileNotFoundError 或跨平台兼容问题。
        """
        cleaned = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        return cleaned or "未命名会话"

    @staticmethod
    def _format_markdown(session: Session, messages: list[Message]) -> str:
        """将会话和消息列表格式化为 Markdown 字符串

        时间戳处理：
        - 数据库存储为 UTC（created_at）
        - 导出时调 .astimezone() 转换为本地时区
        - 不保留 UTC 偏移标识，用户看到的就是本地时间

        Token 统计：
        - 标题区: Session.total_prompt_tokens / total_completion_tokens（会话累计）
        - 每条 AI 消息末尾: Message.prompt_tokens / completion_tokens（单条明细）
        """
        now_local = datetime.now(timezone.utc).astimezone()
        lines = [
            f"# {session.title or '未命名会话'}",
            "",
            f"- 模型: {session.model_name}",
            f"- 导出时间: {now_local.strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Token: {session.total_prompt_tokens} prompt / {session.total_completion_tokens} completion",
            "",
            "---",
            "",
        ]

        for msg in messages:
            local_ts = msg.created_at.astimezone()
            ts_str = local_ts.strftime("%Y-%m-%d %H:%M:%S")
            role_label = "你" if msg.role == "human" else "AI"

            lines.append(f"### {role_label} {ts_str}")
            lines.append("")
            lines.append(msg.content)
            lines.append("")

            if msg.role == "ai" and (msg.prompt_tokens or msg.completion_tokens):
                lines.append(f"> prompt={msg.prompt_tokens}, completion={msg.completion_tokens}")
                lines.append("")

        return "\n".join(lines)

    async def export(self, session_id: int) -> str:
        """将会话导出为 Markdown 文件

        Args:
            session_id: 要导出的会话 ID

        Returns:
            导出的 Markdown 文件绝对路径

        Raises:
            ValueError: 会话不存在或不属于当前用户
        """
        session = await self._backend.get_session(session_id)
        if session is None:
            raise ValueError(f"会话 {session_id} 不存在")
        if session.user_id != self._user_id:
            raise ValueError(f"会话 {session_id} 不属于当前用户")

        messages = await self._backend.get_messages_by_session(session_id)

        export_dir = self._export_dir()
        export_dir.mkdir(parents=True, exist_ok=True)

        title_part = self._sanitize_title(session.title or "未命名会话")
        date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"{title_part}_{date_part}.md"
        filepath = export_dir / filename

        md_content = self._format_markdown(session, messages)
        filepath.write_text(md_content, encoding="utf-8")

        return str(filepath.resolve())
