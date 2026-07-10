"""
程序总入口 —— langchain-chat

启动流程:
  1. ConfigManager 加载配置
  2. StorageFactory 创建存储后端
  3. init_db() 首次运行建表
  4. TUIApp 进入主循环
"""

import asyncio

from src.core.config_manager import ConfigManager
from src.storage.factory import StorageFactory
from src.ui.tui.app import TUIApp


async def main() -> None:
    config = ConfigManager().load()
    backend = StorageFactory.create(config.storage.model_dump())
    await backend.init_db()
    app = TUIApp(backend=backend, config=config)
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
