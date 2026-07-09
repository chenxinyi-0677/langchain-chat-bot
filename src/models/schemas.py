"""
数据模型层 —— Pydantic 模型定义与校验

【What】
定义 User / Session / Message / Preset / UserConfig 五个核心数据实体的
Pydantic 模型，包括创建用变体（xxxCreate）和完整模型（xxx）。

【Why】
- 统一数据校验：确保进入业务层和存储层的数据格式正确
- 序列化/反序列化：模型可自由转换为 dict / JSON，与存储层解耦
- 文档即约束：字段类型、默认值、校验规则形成"活文档"

【Where】
- src/core/ 各 Manager 通过此模块构造和传递数据对象
- src/storage/ 各 Backend 通过此模块反序列化查询结果
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# 辅助函数
# =============================================================================


def _utc_now() -> datetime:
    """返回当前 UTC 时间，供 default_factory 使用"""
    return datetime.now(timezone.utc)


# =============================================================================
# User —— 用户基本信息与偏好
# =============================================================================
# 【What  What】
#   用户实体。存储登录名、默认模型、默认预设等偏好信息。
# 【Why  Why】
#   实现 B4 用户隔离：所有会话/预设/配置通过 user_id 归属到具体用户。
# 【Where Where】
#   user_manager 创建/切换/删除用户时使用；
#   其他 Manager 通过 user_id 过滤数据。
# 【How  How】
#   - username：唯一标识用户，约束为字母/数字/下划线/连字符
#     避免特殊字符污染 F2 导出路径 data/users/{username}/exports/
#   - default_model / default_preset_id：会话默认值，可选
# =============================================================================


class UserBase(BaseModel):
    """User 公用字段（Create / 完整模型共享）"""

    username: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="用户名：唯一标识，仅允许字母/数字/下划线/连字符",
    )
    default_model: Optional[str] = Field(
        None,
        max_length=100,
        description="默认模型名称，新建会话时自动填充",
    )
    default_preset_id: Optional[int] = Field(
        None,
        description="默认预设 ID，新建会话时自动填充",
    )


class UserCreate(UserBase):
    """创建用户时的请求模型（不含 id / 时间戳，由系统自动生成）"""


class User(UserBase):
    """完整用户模型，包含数据库自动生成字段"""

    id: int = Field(..., description="用户 ID，主键，由存储层自增生成")
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="创建时间（UTC），记录用户首次注册时间",
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        description="最后更新时间（UTC），记录用户信息最近修改时间",
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Session —— 会话索引
# =============================================================================
# 【What  What】
#   会话实体。作为多轮对话的容器，关联到具体用户和预设。
# 【Why  Why】
#   实现 C1-C7 会话生命周期管理：创建/加载/保存/重命名/删除/列表/自动标题。
# 【Where Where】
#   session_manager 管理生命周期；
#   chat_engine 读取当前会话的历史消息作为 Memory 上下文。
# 【How  How】
#   - title 创建时可选（None），首轮对话后由 C7 自动生成前 30 字符
#   - total_prompt_tokens / total_completion_tokens 累计统计（E2）
# =============================================================================


class SessionBase(BaseModel):
    """Session 公用字段"""

    user_id: int = Field(..., description="所属用户 ID，关联 User")
    title: Optional[str] = Field(
        None,
        max_length=200,
        description="会话标题。创建时为 None，首轮对话后由 C7 自动生成前 30 字符",
    )
    model_name: str = Field(
        ...,
        max_length=100,
        description="会话使用的模型名称，支持中途切换（A5）",
    )
    preset_id: Optional[int] = Field(
        None,
        description="关联的预设 ID。None 表示不使用预设",
    )


class SessionCreate(SessionBase):
    """创建会话时的请求模型（不含 id / 统计 / 时间戳）"""


class Session(SessionBase):
    """完整会话模型"""

    id: int = Field(..., description="会话 ID，主键，由存储层自增生成")
    total_prompt_tokens: int = Field(
        0,
        ge=0,
        description="累计 prompt tokens 数（E2 用量统计）",
    )
    total_completion_tokens: int = Field(
        0,
        ge=0,
        description="累计 completion tokens 数（E2 用量统计）",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="创建时间（UTC）",
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        description="最后更新时间（UTC），每轮对话结束后更新",
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Message —— 单条对话消息
# =============================================================================
# 【What  What】
#   单轮对话消息。记录一次交互中用户或 LLM 的发言内容及 token 消耗。
# 【Why  Why】
#   - A1/A2：多轮会话依赖消息历史维持上下文
#   - E1：对话搜索在此模型上按关键词匹配
#   - E2/F1：token 统计和导出基于此模型
# 【Where Where】
#   chat_engine 完成流式输出后写入；
#   session_manager 加载历史会话时读取。
# 【How  How】
#   - role 限定为 human(用户)/ai(LLM)/system(预设系统消息) 三种
#   - 不含 updated_at：消息写入后不可修改（不可变性）
# =============================================================================


class MessageBase(BaseModel):
    """Message 公用字段"""

    session_id: int = Field(..., description="所属会话 ID，关联 Session")
    role: Literal["human", "ai", "system"] = Field(
        ...,
        description="消息角色：human（用户）/ ai（LLM）/ system（系统预设）",
    )
    content: str = Field(
        ...,
        description="消息内容。human/ai 为纯文本，system 包含预设指令",
    )
    prompt_tokens: int = Field(
        0,
        ge=0,
        description="该条消息消耗的 prompt tokens（LLM 统计）",
    )
    completion_tokens: int = Field(
        0,
        ge=0,
        description="该条消息消耗的 completion tokens（LLM 统计）",
    )


class MessageCreate(MessageBase):
    """创建消息时的请求模型"""


class Message(MessageBase):
    """完整消息模型"""

    id: int = Field(..., description="消息 ID，主键，由存储层自增生成")
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="创建时间（UTC），消息写入时间，不可变",
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Preset —— 角色预设
# =============================================================================
# 【What  What】
#   角色预设。包含名称、描述、系统提示词，用于快速设定 LLM 角色行为。
# 【Why  Why】
#   实现 D1-D4：内置预设（所有用户共享）+ 自定义预设（用户隔离管理）。
# 【Where Where】
#   preset_manager 负责 CRUD；
#   session_manager 新建会话时可选关联。
# 【How  How】
#   - user_id = None 表示为系统内置预设（D1），由 config/presets.yaml 加载
#   - is_builtin 标记不可由用户删除
# =============================================================================


class PresetBase(BaseModel):
    """Preset 公用字段"""

    user_id: Optional[int] = Field(
        None,
        description="所属用户 ID。None = 系统内置预设，所有用户共享",
    )
    name: str = Field(
        ...,
        max_length=100,
        description="预设名称，如「翻译助手」「代码专家」",
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="预设描述，简要说明角色定位和适用场景",
    )
    system_prompt: str = Field(
        ...,
        description="系统提示词，完整的角色设定指令（TEXT 无长度限制）",
    )
    is_builtin: bool = Field(
        False,
        description="是否为系统内置预设。True 时用户不可删除/编辑",
    )


class PresetCreate(PresetBase):
    """创建预设时的请求模型"""


class Preset(PresetBase):
    """完整预设模型"""

    id: int = Field(..., description="预设 ID，主键，由存储层自增生成")
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="创建时间（UTC）",
    )
    updated_at: datetime = Field(
        default_factory=_utc_now,
        description="最后更新时间（UTC）",
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# UserConfig —— 用户偏好键值对
# =============================================================================
# 【What  What】
#   用户级键值对存储，用于保存个性化偏好（如主题、语言、每页显示条数）。
# 【Why  Why】
#   实现 B4 用户隔离 + 轻量扩展：无需为每个偏好新增字段，键值对灵活。
# 【Where Where】
#   config_manager 或用户设置功能使用。
# 【How  How】
#   - 无需 created_at：键值对是配置项，非业务实体生命周期
#   - key + user_id 在存储层应构成唯一联合索引
# =============================================================================


class UserConfigBase(BaseModel):
    """UserConfig 公用字段"""

    user_id: int = Field(..., description="所属用户 ID，关联 User")
    key: str = Field(
        ...,
        max_length=100,
        description="配置键名，如 'theme'、'language'",
    )
    value: str = Field(
        ...,
        max_length=500,
        description="配置值，如 'dark'、'zh-CN'",
    )


class UserConfigCreate(UserConfigBase):
    """创建设置项时的请求模型"""


class UserConfig(UserConfigBase):
    """完整用户配置模型"""

    id: int = Field(..., description="配置 ID，主键，由存储层自增生成")
    updated_at: datetime = Field(
        default_factory=_utc_now,
        description="最后更新时间（UTC），每次修改时更新",
    )

    model_config = ConfigDict(from_attributes=True)
