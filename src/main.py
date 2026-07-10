"""
程序总入口 —— langchain-chat

启动方式:
  python -m src.main          # [推荐] 项目根目录下运行
  python src/main.py          # 兼容方式，依赖下方 sys.path 修正

启动流程:
  1. setup_logging() 初始化结构化日志
  2. ConfigManager 加载配置
  3. StorageFactory 创建存储后端
  4. init_db() 首次运行建表
  5. TUIApp 进入主循环
"""

import asyncio
import sys
from pathlib import Path

# 允许 python src/main.py 直接运行（-m 方式不需要此修正）
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger, setup_logging
from src.core.preset_manager import PresetManager
from src.storage.factory import StorageFactory
from src.ui.tui.app import TUIApp

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("Application starting")

    config = ConfigManager().load()
    backend = StorageFactory.create({"storage": config.storage.model_dump()})
    await backend.init_db()
    await PresetManager.sync_builtin_presets(backend)
    app = TUIApp(backend=backend, config=config)
    await app.run()

    logger.info("Application stopped")


if __name__ == "__main__":
    asyncio.run(main())
