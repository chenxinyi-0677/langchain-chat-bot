"""
存储后端工厂 —— StorageFactory

【What】
根据 config.yaml 的 storage.type 配置实例化对应的存储后端。

【Why】
实现 4.2 节工厂模式：业务层只需传入配置字典，无需感知具体后端类。

【Where】
应用启动时由 config_manager 读取配置后调用，返回 StorageBackend 实例。
"""

from typing import Any

from src.storage.base import StorageBackend
from src.storage.sqlite_backend import SQLiteBackend


class StorageFactory:
    """根据配置创建存储后端实例的工厂类"""

    # 注册的后端映射表（扩展新后端时在此添加）
    _BACKENDS: dict[str, type[StorageBackend]] = {
        "sqlite": SQLiteBackend,
    }

    @classmethod
    def create(cls, config: dict[str, Any]) -> StorageBackend:
        """根据配置字典创建存储后端实例

        Args:
            config: 全局配置字典，结构如
                {
                    "storage": {
                        "type": "sqlite",
                        "sqlite": {"path": "data/sqlite/app.db"},
                    }
                }

        Returns:
            StorageBackend 实例

        Raises:
            ValueError: storage.type 未知或未配置
        """
        storage_cfg = config.get("storage", {})
        backend_type = storage_cfg.get("type", "sqlite")

        backend_cls = cls._BACKENDS.get(backend_type)
        if backend_cls is None:
            raise ValueError(
                f"未知的存储类型: {backend_type!r}。可选: {', '.join(cls._BACKENDS)}"
            )

        backend_cfg = storage_cfg.get(backend_type, {})
        return backend_cls(**backend_cfg)
