"""
结构化日志 —— JSONFormatter + setup

【What】
- JSONFormatter: 将标准 logging.LogRecord 输出为单行 JSON
- setup_logging: 读取 config/logging.yaml 并配置全局日志系统

【覆盖需求】
G2(JSON格式结构化日志, 配置文件独立管理)

【Why】
- 标准库 logging + 自定义 Formatter，无需引入 structlog 等第三方
- 每行一个 JSON 对象，便于后续按 level/logger/timestamp 检索

【Where】
- main.py 启动时调用 setup_logging() 完成全局配置
- 各模块通过 logging.getLogger(__name__) 使用
"""

import json
import logging
import logging.config
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# LogRecord 标准属性（extra 传入的自定义属性不在此集合中）
_STANDARD_RECORD_KEYS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName",
})


class JSONFormatter(logging.Formatter):
    """将日志记录格式化为单行 JSON

    基础字段: timestamp, level, logger, message
    额外字段: extra 参数传入的自定义属性自动合并到 JSON 中

    用法:
        _LOGGER.info("User created", extra={"username": "alice", "user_id": 1})
        → {"timestamp":"...","level":"INFO","logger":"...","message":"User created","username":"alice","user_id":1}
    """

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_KEYS and not key.startswith("_"):
                obj[key] = value
        return json.dumps(obj, ensure_ascii=False)


def setup_logging() -> None:
    """读取 config/logging.yaml 并配置全局日志系统

    自动创建 data/logs/ 目录（RotatingFileHandler 不会自动建父目录）。
    先 mkdir 再 dictConfig，避免重复 SQLite 的坑。
    """
    log_dir = _PROJECT_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    config_path = _PROJECT_ROOT / "config" / "logging.yaml"
    if not config_path.exists():
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning("logging.yaml not found, using basicConfig")
        return

    import yaml

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """获取 Logger 实例"""
    return logging.getLogger(name)
