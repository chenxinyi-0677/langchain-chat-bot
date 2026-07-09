"""
pytest 全局 Fixture

【What】
提供测试间隔离的临时 SQLite 后端实例。

【Why】
- 遵循 AGENTS.md 测试约定：使用 tmp_path 生成临时 SQLite 文件，避免 :memory:
- 每个测试函数获得独立的 DB 文件，互不干扰
"""

from pathlib import Path

import pytest

from src.models.schemas import User, UserCreate
from src.storage.sqlite_backend import SQLiteBackend


@pytest.fixture
async def tmp_sqlite_backend(tmp_path: Path) -> SQLiteBackend:
    """返回已 init_db 的 SQLiteBackend 实例，指向临时文件"""
    db_path = tmp_path / "test.db"
    backend = SQLiteBackend(path=str(db_path))
    await backend.init_db()
    yield backend
    await backend.close()


@pytest.fixture
async def test_user(tmp_sqlite_backend: SQLiteBackend) -> User:
    """返回一个已持久化的测试用户"""
    return await tmp_sqlite_backend.create_user(UserCreate(username="test_user"))
