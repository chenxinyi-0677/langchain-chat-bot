"""
模型层测试骨架 —— Pydantic 模型校验与构造

【What】
验证 src.models.schemas 中 5 个数据模型的字段校验、默认值、
序列化/反序列化逻辑正确。

【Why】
确保数据模型定义与需求文档 4.3 节一致，防止对 schemas.py 的
修改引入兼容性问题。

【Where】
与 src/models/schemas.py 一一对应。
"""

import pytest

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


# =============================================================================
# Fixtures —— User
# =============================================================================


@pytest.fixture
def user_create_data() -> dict:
    """返回标准 UserCreate 初始化数据"""
    return {
        "username": "test_user",
        "default_model": "gpt-4o",
        "default_preset_id": 1,
    }


@pytest.fixture
def user_create_instance(user_create_data: dict) -> UserCreate:
    """返回标准的 UserCreate 实例"""
    return UserCreate(**user_create_data)


@pytest.fixture
def user_instance(user_create_data: dict) -> User:
    """返回完整的 User 实例（含 id 和时间戳）"""
    return User(id=1, **user_create_data)


# =============================================================================
# Fixtures —— Session
# =============================================================================


@pytest.fixture
def session_create_data() -> dict:
    """返回标准 SessionCreate 初始化数据（title=None 模拟新建场景）"""
    return {
        "user_id": 1,
        "title": None,
        "model_name": "gpt-4o",
        "preset_id": None,
    }


@pytest.fixture
def session_create_instance(session_create_data: dict) -> SessionCreate:
    """返回标准的 SessionCreate 实例"""
    return SessionCreate(**session_create_data)


@pytest.fixture
def session_instance(session_create_data: dict) -> Session:
    """返回完整的 Session 实例（含 id / 统计 / 时间戳）"""
    data = {**session_create_data, "title": "测试会话"}
    return Session(id=1, **data)


# =============================================================================
# Fixtures —— Message
# =============================================================================


@pytest.fixture
def message_create_data() -> dict:
    """返回标准 MessageCreate 初始化数据"""
    return {
        "session_id": 1,
        "role": "human",
        "content": "你好，请问今天天气怎么样？",
        "prompt_tokens": 15,
        "completion_tokens": 0,
    }


@pytest.fixture
def message_create_instance(message_create_data: dict) -> MessageCreate:
    """返回标准的 MessageCreate 实例"""
    return MessageCreate(**message_create_data)


@pytest.fixture
def message_instance(message_create_data: dict) -> Message:
    """返回完整的 Message 实例（含 id 和时间戳）"""
    data = {**message_create_data, "role": "ai", "content": "今天天气晴朗。"}
    return Message(id=1, **data)


# =============================================================================
# Fixtures —— Preset
# =============================================================================


@pytest.fixture
def preset_create_data() -> dict:
    """返回标准 PresetCreate 初始化数据"""
    return {
        "user_id": None,
        "name": "翻译助手",
        "description": "专业的语言翻译助手",
        "system_prompt": "你是一名专业的翻译。请准确翻译用户输入的内容。",
        "is_builtin": True,
    }


@pytest.fixture
def preset_create_instance(preset_create_data: dict) -> PresetCreate:
    """返回标准的 PresetCreate 实例"""
    return PresetCreate(**preset_create_data)


@pytest.fixture
def preset_instance(preset_create_data: dict) -> Preset:
    """返回完整的 Preset 实例（含 id 和时间戳）"""
    return Preset(id=1, **preset_create_data)


# =============================================================================
# Fixtures —— UserConfig
# =============================================================================


@pytest.fixture
def config_create_data() -> dict:
    """返回标准 UserConfigCreate 初始化数据"""
    return {
        "user_id": 1,
        "key": "theme",
        "value": "dark",
    }


@pytest.fixture
def config_create_instance(config_create_data: dict) -> UserConfigCreate:
    """返回标准的 UserConfigCreate 实例"""
    return UserConfigCreate(**config_create_data)


@pytest.fixture
def config_instance(config_create_data: dict) -> UserConfig:
    """返回完整的 UserConfig 实例（含 id 和时间戳）"""
    return UserConfig(id=1, **config_create_data)


# =============================================================================
# 占位测试用例（后续逐步补充）
# =============================================================================


class TestUserModel:
    """User 模型校验测试（骨架）"""

    def test_username_regex_valid(self, user_create_instance: UserCreate):
        """TODO: 合法的 username 应通过校验"""
        pass

    def test_username_regex_invalid(self):
        """TODO: 含特殊字符的 username 应拒绝"""
        pass

    def test_username_min_length(self):
        """TODO: 空字符串应拒绝"""
        pass

    def test_user_serialization(self, user_instance: User):
        """TODO: User → dict → User 往返序列化"""
        pass

    def test_user_timestamps_utc(self, user_instance: User):
        """TODO: created_at / updated_at 应为 UTC"""
        pass


class TestSessionModel:
    """Session 模型校验测试（骨架）"""

    def test_title_default_none(self, session_create_instance: SessionCreate):
        """TODO: 新建会话时 title 应默认为 None"""
        pass

    def test_tokens_default_zero(self, session_instance: Session):
        """TODO: total_prompt_tokens / total_completion_tokens 默认 0"""
        pass

    def test_session_serialization(self, session_instance: Session):
        """TODO: Session → dict → Session 往返序列化"""
        pass


class TestMessageModel:
    """Message 模型校验测试（骨架）"""

    def test_role_valid_values(self):
        """TODO: role 只能取 human / ai / system"""
        pass

    def test_role_invalid_value(self):
        """TODO: role 取其他值应拒绝"""
        pass

    def test_tokens_default_zero(self, message_instance: Message):
        """TODO: prompt_tokens / completion_tokens 默认 0"""
        pass

    def test_no_updated_at(self, message_instance: Message):
        """TODO: Message 不应包含 updated_at 字段"""
        pass


class TestPresetModel:
    """Preset 模型校验测试（骨架）"""

    def test_user_id_none_for_builtin(self, preset_instance: Preset):
        """TODO: 内置预设 user_id 应为 None"""
        pass

    def test_description_optional(self):
        """TODO: description 可为 None"""
        pass

    def test_is_builtin_default_false(self):
        """TODO: 非内置预设 is_builtin 默认 False"""
        pass


class TestUserConfigModel:
    """UserConfig 模型校验测试（骨架）"""

    def test_no_created_at(self, config_instance: UserConfig):
        """TODO: UserConfig 不应包含 created_at 字段"""
        pass

    def test_key_value_required(self):
        """TODO: key 和 value 均为必填"""
        pass
