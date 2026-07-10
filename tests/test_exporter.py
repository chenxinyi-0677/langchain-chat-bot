"""
导出单元测试 —— test_exporter

【覆盖需求】
F1(导出Markdown格式)  F2(导出路径+文件名)

【Why】
Exporter 涉及文件 I/O、Markdown 格式化、文件名清理，需独立验证。
存储层透传行为通过 mock 验证（不重复测 backend 的 get_session 逻辑）。
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.exporter import Exporter
from src.models.schemas import Message, MessageCreate, Session, SessionCreate, UserCreate
from src.storage.sqlite_backend import SQLiteBackend


class TestSanitizeTitle:
    """文件名清理"""

    def test_normal_title_preserved(self):
        assert Exporter._sanitize_title("hello") == "hello"

    def test_special_chars_replaced(self):
        result = Exporter._sanitize_title('a/b:c*d?e"f<g>h|i')
        assert result == "a_b_c_d_e_f_g_h_i"

    def test_empty_title_fallback(self):
        result = Exporter._sanitize_title("")
        assert result == "未命名会话"

    def test_whitespace_only_title(self):
        result = Exporter._sanitize_title("   ")
        assert result == "未命名会话"


class TestFormatMarkdown:
    """Markdown 格式化"""

    def test_basic_format(self):
        session = Session(
            id=1, user_id=1, title="测试会话", model_name="gpt-4o",
            total_prompt_tokens=100, total_completion_tokens=50,
            created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        )
        msgs = [
            Message(
                id=1, session_id=1, role="human", content="你好",
                created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            ),
            Message(
                id=2, session_id=1, role="ai", content="你好！有什么我可以帮助你的吗？",
                prompt_tokens=10, completion_tokens=20,
                created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            ),
        ]
        md = Exporter._format_markdown(session, msgs)
        assert "# 测试会话" in md
        assert "- 模型: gpt-4o" in md
        assert "- Token: 100 prompt / 50 completion" in md
        assert "### 你" in md
        assert "你好" in md
        assert "### AI" in md
        assert "你好！有什么我可以帮助你的吗？" in md
        assert "prompt=10, completion=20" in md

    def test_ai_message_without_tokens_omits_stats(self):
        session = Session(
            id=1, user_id=1, title="s", model_name="gpt-4o",
            created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        )
        msgs = [
            Message(
                id=1, session_id=1, role="ai", content="no tokens",
                created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            ),
        ]
        md = Exporter._format_markdown(session, msgs)
        assert "prompt=" not in md

    def test_human_message_no_token_line(self):
        session = Session(
            id=1, user_id=1, title="s", model_name="gpt-4o",
            created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
        )
        msgs = [
            Message(
                id=1, session_id=1, role="human", content="hi",
                created_at=datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc),
            ),
        ]
        md = Exporter._format_markdown(session, msgs)
        assert "### 你" in md
        assert "prompt=" not in md


class TestExportIntegration:
    """端到端导出（依赖真实 SQLite）"""

    async def test_export_creates_markdown_file(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(
            UserCreate(username="testuser"),
        )
        session = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, title="测试会话", model_name="gpt-4o"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(session_id=session.id, role="human", content="你好"),
        )
        await tmp_sqlite_backend.create_message(
            MessageCreate(
                session_id=session.id, role="ai", content="hello",
                prompt_tokens=5, completion_tokens=10,
            ),
        )

        exporter = Exporter(
            backend=tmp_sqlite_backend,
            user_id=user.id,
            username=user.username,
        )
        path = await exporter.export(session.id)

        assert path.endswith(".md")
        content = Path(path).read_text(encoding="utf-8")
        assert "# 测试会话" in content
        assert "你好" in content
        assert "hello" in content
        assert "prompt=5, completion=10" in content

    async def test_export_unknown_session_raises(self, tmp_sqlite_backend: SQLiteBackend):
        exporter = Exporter(backend=tmp_sqlite_backend, user_id=1, username="u")
        with pytest.raises(ValueError, match="不存在"):
            await exporter.export(999)

    async def test_export_wrong_user_raises(self, tmp_sqlite_backend: SQLiteBackend):
        user = await tmp_sqlite_backend.create_user(
            UserCreate(username="owner"),
        )
        session = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, title="s", model_name="gpt-4o"),
        )
        exporter = Exporter(backend=tmp_sqlite_backend, user_id=999, username="other")
        with pytest.raises(ValueError, match="不属于当前用户"):
            await exporter.export(session.id)

    async def test_export_creates_directory(self, tmp_sqlite_backend: SQLiteBackend):
        """验证导出目录自动创建（吸取 init_db 的教训）"""
        user = await tmp_sqlite_backend.create_user(
            UserCreate(username="dir_test"),
        )
        session = await tmp_sqlite_backend.create_session(
            SessionCreate(user_id=user.id, title="dir", model_name="gpt-4o"),
        )
        exporter = Exporter(backend=tmp_sqlite_backend, user_id=user.id, username=user.username)
        path = await exporter.export(session.id)
        assert Path(path).parent.exists()
