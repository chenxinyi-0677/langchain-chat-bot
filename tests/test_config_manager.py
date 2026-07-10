"""
配置管理单元测试 —— test_config_manager

【覆盖需求】
A4(.env → API_BASE_URL / API_KEY / MODEL_NAME)
G1(config.yaml → llm.timeout / llm.max_retries)
G3(区分两个来源，统一建模)
"""

from pathlib import Path

import pytest

from src.core.config_manager import (
    AppConfig,
    ConfigManager,
    EnvSettings,
    LLMConfig,
    SqliteConfig,
    StorageConfig,
)

# =====================================================================
# 模型单元测试
# =====================================================================


class TestEnvSettings:
    """pydantic-settings .env 加载"""

    def test_default_values(self, tmp_path: Path):
        dotenv = tmp_path / ".env"  # 不存在的文件，防止读到真实 .env
        env = EnvSettings(_env_file=str(dotenv))
        assert env.api_base_url == "https://api.openai.com/v1"
        assert env.api_key == ""
        assert env.model_name == "gpt-4o"

    def test_load_from_env_file(self, tmp_path: Path):
        dotenv = tmp_path / ".env"
        dotenv.write_text(
            "API_BASE_URL=https://custom.api.com\nAPI_KEY=sk-test\nMODEL_NAME=gpt-4o-mini\n",
        )
        env = EnvSettings(_env_file=str(dotenv))
        assert env.api_base_url == "https://custom.api.com"
        assert env.api_key == "sk-test"
        assert env.model_name == "gpt-4o-mini"

    def test_env_var_overrides_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        dotenv = tmp_path / ".env"
        dotenv.write_text("API_KEY=from-file\n")
        monkeypatch.setenv("API_KEY", "from-env-var")
        env = EnvSettings(_env_file=str(dotenv))
        # 环境变量优先级高于 .env 文件
        assert env.api_key == "from-env-var"


class TestLLMConfig:
    def test_default_values(self):
        cfg = LLMConfig()
        assert cfg.timeout == 120
        assert cfg.max_retries == 3

    def test_custom_values(self):
        cfg = LLMConfig(timeout=60, max_retries=5)
        assert cfg.timeout == 60
        assert cfg.max_retries == 5


class TestStorageConfig:
    def test_default_sqlite(self):
        cfg = StorageConfig()
        assert cfg.type == "sqlite"
        assert cfg.sqlite.path == "data/sqlite/chat.db"

    def test_custom_sqlite_path(self):
        cfg = StorageConfig(sqlite=SqliteConfig(path="/tmp/test.db"))
        assert cfg.sqlite.path == "/tmp/test.db"


class TestAppConfig:
    def test_default_config(self):
        cfg = AppConfig()
        assert cfg.llm.timeout == 120
        assert cfg.storage.type == "sqlite"

    def test_custom_nested(self):
        cfg = AppConfig(
            llm=LLMConfig(timeout=30),
            storage=StorageConfig(type="sqlite"),
        )
        assert cfg.llm.timeout == 30


# =====================================================================
# ConfigManager 集成测试
# =====================================================================


class TestConfigManager:
    def test_load_defaults_when_no_files(self, tmp_path: Path):
        mgr = ConfigManager(
            env_file=str(tmp_path / ".env"),
            config_path=str(tmp_path / "config.yaml"),
        )
        config = mgr.load()
        assert isinstance(config, AppConfig)
        assert config.llm.timeout == 120
        assert config.storage.type == "sqlite"
        assert config.env.model_name == "gpt-4o"

    def test_load_from_yaml(self, tmp_path: Path):
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "llm:\n  timeout: 30\n  max_retries: 5\nstorage:\n  type: sqlite\n",
        )
        mgr = ConfigManager(
            env_file=str(tmp_path / ".env"),
            config_path=str(config_yaml),
        )
        config = mgr.load()
        assert config.llm.timeout == 30
        assert config.llm.max_retries == 5
        assert config.storage.type == "sqlite"

    def test_load_full_config(self, tmp_path: Path):
        dotenv = tmp_path / ".env"
        dotenv.write_text("API_KEY=sk-real\nMODEL_NAME=claude-3\n")
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text(
            "llm:\n  timeout: 60\nstorage:\n  sqlite:\n    path: custom/db.sqlite\n",
        )
        mgr = ConfigManager(
            env_file=str(dotenv),
            config_path=str(config_yaml),
        )
        config = mgr.load()
        assert config.env.api_key == "sk-real"
        assert config.env.model_name == "claude-3"
        assert config.llm.timeout == 60
        assert config.storage.sqlite.path == "custom/db.sqlite"

    def test_yaml_partial_override(self, tmp_path: Path):
        """YAML 只写部分字段，其余应使用默认值"""
        config_yaml = tmp_path / "config.yaml"
        config_yaml.write_text("llm:\n  timeout: 99\n")
        mgr = ConfigManager(
            env_file=str(tmp_path / ".env"),
            config_path=str(config_yaml),
        )
        config = mgr.load()
        assert config.llm.timeout == 99
        assert config.llm.max_retries == 3  # 默认值保留
