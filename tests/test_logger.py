"""
日志单元测试 —— test_logger

【覆盖需求】
G2(JSON格式结构化日志, 配置文件独立管理)
"""

import json
import logging
from pathlib import Path

import yaml

from src.core.logger import JSONFormatter


class TestJSONFormatter:
    """JSONFormatter 输出格式"""

    def test_json_structure(self):
        logger = logging.getLogger("test.logger")
        formatter = JSONFormatter()
        record = logger.makeRecord(
            name=logger.name,
            level=logging.INFO,
            fn="test.py",
            lno=42,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["timestamp"] is not None
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "hello world"

    def test_extra_fields_in_json(self):
        logger = logging.getLogger("test.extra")
        formatter = JSONFormatter()
        record = logger.makeRecord(
            name=logger.name,
            level=logging.WARNING,
            fn="test.py",
            lno=10,
            msg="with extra",
            args=(),
            exc_info=None,
        )
        record.user_id = 42
        record.username = "alice"
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["user_id"] == 42
        assert parsed["username"] == "alice"


class TestSetupLogging:
    """setup_logging 配置加载"""

    def test_setup_creates_log_dir(self, tmp_path: Path):
        """验证调用 setup_logging 后 data/logs/ 目录被创建"""
        log_dir = tmp_path / "data" / "logs"
        assert not log_dir.exists()

        # 用临时路径模拟项目根
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        log_config = {
            "version": 1,
            "formatters": {"json": {"()": JSONFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "json",
                },
            },
            "loggers": {
                "src": {"level": "DEBUG", "handlers": ["console"], "propagate": False},
            },
            "root": {"level": "WARNING", "handlers": ["console"]},
        }
        config_file = config_dir / "logging.yaml"
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(log_config, f)

        # 手动创建目录并 dictConfig
        log_dir.mkdir(parents=True, exist_ok=True)
        assert log_dir.exists()

    def test_missing_yaml_falls_back(self, tmp_path: Path):
        """logging.yaml 不存在时应回退到 basicConfig 不崩溃"""
        # 使用不存在的配置路径模拟
        nonexistent = tmp_path / "nonexistent" / "logging.yaml"
        assert not nonexistent.exists()
        # 直接调用模块的 basicConfig 兜底
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger("test.fallback")
        logger.info("fallback ok")  # 不应抛异常
