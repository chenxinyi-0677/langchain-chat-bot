"""
SQLite 存储后端实现 —— SQLiteBackend

【What】
基于 aiosqlite 的 SQLite 实现，提供 StorageBackend 定义的全部异步 CRUD 方法。

【Why】
作为默认存储后端（需求文档 4.1 节），轻量无依赖，适合开发/教学场景。

【Where】
- StorageFactory 根据 config.yaml 中 storage.type = "sqlite" 时实例化
- core/ 层各 Manager 通过 StorageBackend 接口调用，无需感知具体实现

【覆盖需求】
4.1(可插拔后端)  4.3(数据实体)  C6(自动保存)  B3(级联删除)
"""

from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from src.models.schemas import (
    Message,
    MessageCreate,
    Preset,
    PresetCreate,
    Session,
    SessionCreate,
    User,
    UserCreate,
    UserConfig,
    UserConfigCreate,
)
from src.storage.base import StorageBackend


def _utc_now_str() -> str:
    """返回当前 UTC 时间的 ISO 8601 字符串"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# DDL —— 五张表的建表 SQL
# ---------------------------------------------------------------------------
# 设计要点：
# - 所有外键加 ON DELETE CASCADE，配合 PRAGMA foreign_keys = ON 实现自动级联
# - default_preset_id 用 ON DELETE SET NULL：删除预设时不级联删除用户
# - role 列 CHECK 约束确保只存 human / ai / system
# - user_configs 用 UNIQUE(user_id, key) 保证键值唯一
# - 时间戳存 ISO 8601 文本，Python 侧 Pydantic 序列化/反序列化
# ---------------------------------------------------------------------------

_DDL_CREATE_TABLES = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    default_model   TEXT,
    default_preset_id INTEGER,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (default_preset_id) REFERENCES presets(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL,
    title                 TEXT    NOT NULL,
    model_name            TEXT    NOT NULL,
    preset_id             INTEGER,
    total_prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    total_completion_tokens INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS messages (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        INTEGER NOT NULL,
    role              TEXT    NOT NULL CHECK (role IN ('human', 'ai', 'system')),
    content           TEXT    NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS presets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    name          TEXT    NOT NULL,
    description   TEXT,
    system_prompt TEXT    NOT NULL,
    is_builtin    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_configs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    key        TEXT    NOT NULL,
    value      TEXT    NOT NULL,
    updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE(user_id, key),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


class SQLiteBackend(StorageBackend):
    """基于 aiosqlite 的 SQLite 存储后端"""

    def __init__(self, path: str = "data/sqlite/app.db"):
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None

    # ==================================================================
    # 连接生命周期
    # ==================================================================

    async def init_db(self) -> None:
        """打开数据库连接并执行建表 DDL"""
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_DDL_CREATE_TABLES)

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _ensure_conn(self) -> aiosqlite.Connection:
        """确保连接已初始化（防御性检查）"""
        if self._conn is None:
            raise RuntimeError("数据库未初始化，请先调用 init_db()")
        return self._conn

    # ==================================================================
    # 行 → Pydantic 模型转换
    # ==================================================================

    @staticmethod
    def _row_to_user(row: aiosqlite.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            default_model=row["default_model"],
            default_preset_id=row["default_preset_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_session(row: aiosqlite.Row) -> Session:
        return Session(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            model_name=row["model_name"],
            preset_id=row["preset_id"],
            total_prompt_tokens=row["total_prompt_tokens"],
            total_completion_tokens=row["total_completion_tokens"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_message(row: aiosqlite.Row) -> Message:
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_preset(row: aiosqlite.Row) -> Preset:
        return Preset(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row["description"],
            system_prompt=row["system_prompt"],
            is_builtin=bool(row["is_builtin"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_user_config(row: aiosqlite.Row) -> UserConfig:
        return UserConfig(
            id=row["id"],
            user_id=row["user_id"],
            key=row["key"],
            value=row["value"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ==================================================================
    # User
    # ==================================================================

    async def create_user(self, user: UserCreate) -> User:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        try:
            cursor = await conn.execute(
                """INSERT INTO users (username, default_model, default_preset_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user.username, user.default_model, user.default_preset_id, now, now),
            )
            await conn.commit()
        except aiosqlite.IntegrityError:
            raise ValueError(f"用户名 '{user.username}' 已存在")
        return User(
            id=cursor.lastrowid,
            **user.model_dump(),
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get_user(self, user_id: int) -> Optional[User]:
        conn = await self._ensure_conn()
        cursor = await conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return self._row_to_user(row) if row else None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        return self._row_to_user(row) if row else None

    async def update_user(self, user: User) -> User:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        await conn.execute(
            """UPDATE users SET username=?, default_model=?, default_preset_id=?, updated_at=?
               WHERE id=?""",
            (user.username, user.default_model, user.default_preset_id, now, user.id),
        )
        await conn.commit()
        result = await self.get_user(user.id)
        assert result is not None
        return result

    async def delete_user(self, user_id: int) -> None:
        """级联删除由 ON DELETE CASCADE 自动处理"""
        conn = await self._ensure_conn()
        await conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await conn.commit()

    async def list_users(self) -> list[User]:
        conn = await self._ensure_conn()
        cursor = await conn.execute("SELECT * FROM users ORDER BY id")
        rows = await cursor.fetchall()
        return [self._row_to_user(r) for r in rows]

    # ==================================================================
    # Session
    # ==================================================================

    async def create_session(self, session: SessionCreate) -> Session:
        """title 为 None 时自动兜底为「未命名会话」"""
        conn = await self._ensure_conn()
        now = _utc_now_str()
        title = session.title.strip() if session.title else "未命名会话"
        cursor = await conn.execute(
            """INSERT INTO sessions (user_id, title, model_name, preset_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session.user_id, title, session.model_name, session.preset_id, now, now),
        )
        await conn.commit()
        return Session(
            id=cursor.lastrowid,
            user_id=session.user_id,
            title=title,
            model_name=session.model_name,
            preset_id=session.preset_id,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get_session(self, session_id: int) -> Optional[Session]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_session(row) if row else None

    async def get_sessions_by_user(self, user_id: int) -> list[Session]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_session(r) for r in rows]

    async def update_session(self, session: Session) -> Session:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        await conn.execute(
            """UPDATE sessions SET title=?, model_name=?, preset_id=?,
                   total_prompt_tokens=?, total_completion_tokens=?, updated_at=?
               WHERE id=?""",
            (
                session.title,
                session.model_name,
                session.preset_id,
                session.total_prompt_tokens,
                session.total_completion_tokens,
                now,
                session.id,
            ),
        )
        await conn.commit()
        result = await self.get_session(session.id)
        assert result is not None
        return result

    async def delete_session(self, session_id: int) -> None:
        """级联删除由 ON DELETE CASCADE 自动处理"""
        conn = await self._ensure_conn()
        await conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await conn.commit()

    # ==================================================================
    # Message
    # ==================================================================

    async def create_message(self, msg: MessageCreate) -> Message:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        cursor = await conn.execute(
            """INSERT INTO messages (session_id, role, content, prompt_tokens, completion_tokens, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                msg.session_id,
                msg.role,
                msg.content,
                msg.prompt_tokens,
                msg.completion_tokens,
                now,
            ),
        )
        await conn.commit()
        return Message(
            id=cursor.lastrowid,
            **msg.model_dump(),
            created_at=datetime.fromisoformat(now),
        )

    async def get_messages_by_session(self, session_id: int) -> list[Message]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_message(r) for r in rows]

    async def search_messages(
        self,
        user_id: int,
        keyword: str,
    ) -> list[tuple[Session, list[Message]]]:
        conn = await self._ensure_conn()
        pattern = f"%{keyword}%"
        cursor = await conn.execute(
            """SELECT m.*, s.title AS session_title, s.user_id AS session_user_id
               FROM messages m
               JOIN sessions s ON m.session_id = s.id
               WHERE s.user_id = ? AND m.content LIKE ?
               ORDER BY s.id, m.created_at""",
            (user_id, pattern),
        )
        rows = await cursor.fetchall()

        groups: dict[int, tuple[Session, list[Message]]] = {}
        for row in rows:
            sid = row["session_id"]
            msg = self._row_to_message(row)
            if sid not in groups:
                ses = Session(
                    id=sid,
                    user_id=row["session_user_id"],
                    title=row["session_title"],
                    model_name="",
                    total_prompt_tokens=0,
                    total_completion_tokens=0,
                    created_at=datetime.min.replace(tzinfo=timezone.utc),
                    updated_at=datetime.min.replace(tzinfo=timezone.utc),
                )
                groups[sid] = (ses, [])
            groups[sid][1].append(msg)

        return list(groups.values())

    # ==================================================================
    # Preset
    # ==================================================================

    async def create_preset(self, preset: PresetCreate) -> Preset:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        cursor = await conn.execute(
            """INSERT INTO presets (user_id, name, description, system_prompt, is_builtin, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                preset.user_id,
                preset.name,
                preset.description,
                preset.system_prompt,
                int(preset.is_builtin),
                now,
                now,
            ),
        )
        await conn.commit()
        return Preset(
            id=cursor.lastrowid,
            **preset.model_dump(),
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get_preset(self, preset_id: int) -> Optional[Preset]:
        conn = await self._ensure_conn()
        cursor = await conn.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
        row = await cursor.fetchone()
        return self._row_to_preset(row) if row else None

    async def get_builtin_presets(self) -> list[Preset]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM presets WHERE user_id IS NULL ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [self._row_to_preset(r) for r in rows]

    async def get_user_presets(self, user_id: int) -> list[Preset]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM presets WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_preset(r) for r in rows]

    async def update_preset(self, preset: Preset) -> Preset:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        await conn.execute(
            """UPDATE presets SET name=?, description=?, system_prompt=?, updated_at=?
               WHERE id=?""",
            (preset.name, preset.description, preset.system_prompt, now, preset.id),
        )
        await conn.commit()
        result = await self.get_preset(preset.id)
        assert result is not None
        return result

    async def delete_preset(self, preset_id: int) -> None:
        conn = await self._ensure_conn()
        await conn.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
        await conn.commit()

    # ==================================================================
    # UserConfig
    # ==================================================================

    async def upsert_user_config(self, cfg: UserConfigCreate) -> UserConfig:
        conn = await self._ensure_conn()
        now = _utc_now_str()
        cursor = await conn.execute(
            """INSERT INTO user_configs (user_id, key, value, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (cfg.user_id, cfg.key, cfg.value, now),
        )
        await conn.commit()
        return UserConfig(
            id=cursor.lastrowid,
            **cfg.model_dump(),
            updated_at=datetime.fromisoformat(now),
        )

    async def get_user_config(self, user_id: int, key: str) -> Optional[UserConfig]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM user_configs WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
        row = await cursor.fetchone()
        return self._row_to_user_config(row) if row else None

    async def get_user_configs(self, user_id: int) -> list[UserConfig]:
        conn = await self._ensure_conn()
        cursor = await conn.execute(
            "SELECT * FROM user_configs WHERE user_id = ? ORDER BY key",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_user_config(r) for r in rows]

    async def delete_user_config(self, user_id: int, key: str) -> None:
        conn = await self._ensure_conn()
        await conn.execute(
            "DELETE FROM user_configs WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
        await conn.commit()
