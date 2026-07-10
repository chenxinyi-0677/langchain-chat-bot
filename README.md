# langchain-chat

基于 LangChain 的多轮对话系统，支持流式输出、会话管理、预设 Prompt 和可插拔存储后端。

## 启动

```bash
# 正确方式（推荐）
uv run python -m src.main

# 或（已兼容）
uv run python src\main.py
```

**为什么必须用 `-m`？**

`from src.core.config_manager import ...` 这类导入语句要求 Python 把项目根目录（`langchain-chat/`）加入 `sys.path`。

- `python -m src.main`：Python 自动将当前工作目录加入 `sys.path`，`src` 包可被正常解析
- `python src/main.py`：Python 默认把脚本所在目录（`src/`）加入 `sys.path`，找不到 `src` 包，报 `ModuleNotFoundError`

`main.py` 顶部已加入 `sys.path` 修正，两种方式均可工作，但 `-m` 是 Python 社区的通用规范和推荐做法。

## 首次使用

```bash
# 1. 从模板创建配置
cp .env.example .env

# 2. 编辑 .env，填入真实 API 信息
#    API_BASE_URL=https://api.deepseek.com
#    API_KEY=sk-xxx
#    MODEL_NAME=deepseek-chat

# 3. 启动
uv run python -m src.main
```

## 运行测试

```bash
uv run pytest
```

## 项目结构

见 `AGENTS.md`。
