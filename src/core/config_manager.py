"""
配置加载与管理 —— ConfigManager

【What】
统一加载 .env（敏感信息）和 config.yaml（全局配置），对外暴露 AppConfig。

【覆盖需求】
A4(.env → API_BASE_URL / API_KEY / MODEL_NAME)
G1(config.yaml → llm.timeout / llm.max_retries)
G3(区分 .env 和 config.yaml 两个来源，用 pydantic-settings 统一建模)

【Why】
- .env 仅存敏感信息（API Key 等），不提交版本控制
- config.yaml 存非敏感全局配置，提交版本控制
- 统一入口确保所有模块获取一致的配置视图

【Where】
- main.py 启动时调用 load()，分发 AppConfig 给各 Manager 和 Factory
- StorageFactory 接收 storage 配置段创建后端
- 其他 Manager 通过 AppConfig 读取 LLM 参数、模型名等
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# 配置模型
# =============================================================================


class EnvSettings(BaseSettings):
    """从 .env 加载的敏感配置

    使用 pydantic-settings 自动读取 .env 文件和环境变量。
    环境变量优先级高于 .env 文件。
    """

    api_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI 兼容接口的基础 URL",
    )
    api_key: str = Field(
        default="",
        description="API 密钥，敏感信息，仅从 .env 或环境变量读取",
    )
    model_name: str = Field(
        default="gpt-4o",
        description="默认使用的模型名称",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


class LLMConfig(BaseModel):
    """config.yaml → llm.*  LLM 调用参数"""

    timeout: int = Field(
        default=120,
        ge=1,
        description="LLM 调用超时时间（秒）",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="调用失败时的最大重试次数",
    )


class SqliteConfig(BaseModel):
    """config.yaml → storage.sqlite  SQLite 后端参数"""

    path: str = Field(
        default="data/sqlite/chat.db",
        description="SQLite 数据库文件路径",
    )


class StorageConfig(BaseModel):
    """config.yaml → storage.*  存储后端配置"""

    type: str = Field(
        default="sqlite",
        description="存储后端类型: sqlite / mysql（预留）",
    )
    sqlite: SqliteConfig = Field(default_factory=SqliteConfig)


class AppConfig(BaseModel):
    """应用全局配置，对外暴露的统一模型

    各模块通过此模型获取配置，无需关心数据来源。
    """

    env: EnvSettings = Field(
        default_factory=EnvSettings,
        description="从 .env 加载的敏感配置",
    )
    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM 调用参数",
    )
    storage: StorageConfig = Field(
        default_factory=StorageConfig,
        description="存储后端配置",
    )


# =============================================================================
# ConfigManager
# =============================================================================


class ConfigManager:
    """配置加载管理器

    同步加载（非 async）:
    - load() 仅涉及本地文件读取（open + yaml.parse），均为 CPU 操作
    - 不存在阻塞 IO 等待，加 async 只会增加事件循环开销
    - 在 main.py 启动阶段调用一次，不影响运行时异步链路
    """

    def __init__(
        self,
        env_file: str = ".env",
        config_path: str = "config.yaml",
    ):
        self._env_file = env_file
        self._config_path = config_path

    def load(self) -> AppConfig:
        """加载全部配置并校验

        Returns:
            包含所有配置段的 AppConfig 对象
        """
        env = EnvSettings(_env_file=self._env_file)
        yaml_config = self._load_yaml()
        return AppConfig(
            env=env,
            llm=LLMConfig(**(yaml_config.get("llm", {}))),
            storage=StorageConfig(**(yaml_config.get("storage", {}))),
        )

    def _load_yaml(self) -> dict[str, Any]:
        """读取 config.yaml，文件不存在时返回空 dict"""
        path = Path(self._config_path)
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
