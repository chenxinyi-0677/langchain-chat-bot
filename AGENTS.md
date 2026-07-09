# AGENTS.md — langchain-chat

## 项目概述

基于 LangChain 的多轮会话系统 + 教学项目。全链路异步（asyncio），分层架构，当前 TUI 交互，后期扩展 WebUI。

- **语言**: Python 3.10+
- **环境管理**: uv
- **版本控制**: Git（每步 commit + tag）
- **异步模式**: 全链路 `async/await`
- **交互**: TUI（rich + prompt_toolkit）

---

## 目录结构（严格遵守）

```
langchain-chat/
├── .env                          # 敏感配置 [gitignore]
├── .env.example                  # 环境变量模板
├── config.yaml                   # 全局配置
├── config/
│   ├── presets.yaml              # 系统内置预设 Prompt
│   └── logging.yaml              # 日志配置
├── data/                         # 运行时数据 [gitignore]
│   └── sqlite/
├── src/
│   ├── __init__.py
│   ├── main.py                   # 程序总入口
│   ├── core/                     # 核心业务层（与 UI 完全无关）
│   │   ├── __init__.py
│   │   ├── chat_engine.py        # 对话引擎
│   │   ├── session_manager.py    # 会话生命周期管理
│   │   ├── user_manager.py       # 用户管理
│   │   ├── preset_manager.py     # 预设 Prompt 管理
│   │   └── config_manager.py     # 配置加载与管理
│   ├── models/                   # 数据模型层
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic 模型
│   ├── storage/                  # 存储层（可插拔后端）
│   │   ├── __init__.py
│   │   ├── base.py               # 抽象基类
│   │   ├── factory.py            # 工厂模式
│   │   ├── sqlite_backend.py     # SQLite 实现
│   │   ├── mysql_backend.py      # MySQL 实现
│   │   └── file_backend.py       # 文件系统实现
│   ├── interface/                # UI 接口定义层
│   │   ├── __init__.py
│   │   └── ui_protocol.py        # UI 协议接口
│   └── ui/                       # UI 实现层
│       ├── __init__.py
│       ├── tui/
│       │   ├── __init__.py
│       │   ├── app.py            # TUI 主应用
│       │   ├── chat_view.py      # 对话视图
│       │   ├── menu_view.py      # 菜单视图
│       │   └── widgets.py        # 复用组件
│       └── web/                  # WebUI 预留
│           └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_chat_engine.py
│   ├── test_session_manager.py
│   ├── test_user_manager.py
│   └── test_storage.py
├── scripts/
│   └── init_db.py
├── docs/
│   └── architecture.md
├── pyproject.toml
├── requirements.txt
└── .gitignore
```

---

## 分层架构

| 层次 | 目录 | 职责 | 依赖方向 |
|------|------|------|----------|
| **业务层** | `src/core/` | 对话引擎、会话/用户/预设/配置管理 | → models, storage, interface |
| **数据模型层** | `src/models/` | Pydantic 数据模型定义与校验 | → 无（纯定义） |
| **存储层** | `src/storage/` | 可插拔后端（SQLite/MySQL/File） | → models |
| **接口定义层** | `src/interface/` | UI 协议抽象（TUI/WebUI 共同遵守） | → models |
| **UI 实现层** | `src/ui/` | TUI 实现 / WebUI 预留 | → interface, core |

**数据流**: UI → interface (协议) → core (业务) → storage (持久化)

**核心约束**: `core/` 中的代码 **不能** 直接引用 `ui/` 中的任何内容，必须通过 `interface/` 解耦。

---

## 命名规范

### 文件与目录
- 全小写 + 下划线（snake_case）
- 测试文件: `test_<模块名>.py`
- 目录名语义化: `core/`, `models/`, `storage/`, `interface/`, `ui/`

### 类
- **PascalCase**
- 业务类: `<功能>Manager` (如 `SessionManager`, `UserManager`)
- 存储后端: `<数据库>Backend` (如 `SQLiteBackend`, `MySQLBackend`)
- 工厂: `StorageFactory`
- 数据模型: `User`, `Session`, `Message`, `Preset`, `UserConfig`

### 函数与方法
- snake_case
- 异步函数前缀 `async def`
- 变量/参数: snake_case

### 数据库表与字段
- 表名: 全小写复数 (`users`, `sessions`, `messages`, `presets`, `user_configs`)
- 字段: snake_case

---

## 技术栈约束

### 必须使用的依赖
| 包 | 用途 |
|----|------|
| `langchain==1.3.11` | LLM 应用框架 |
| `langchain-core==1.4.8` | 核心抽象 |
| `langchain-openai==1.3.2` | OpenAI 兼容接口 |
| `aiosqlite` | SQLite 异步驱动（默认） |
| `aiomysql` | MySQL 异步驱动 |
| `rich` | 终端富文本 |
| `prompt_toolkit` | 高级命令行输入 |
| `pydantic` | 数据模型 |
| `pydantic-settings` | 配置管理 |
| `python-dotenv` | .env 加载 |
| `pyyaml` | YAML 解析 |

### 开发工具
| 工具 | 用途 |
|------|------|
| `pytest` + `pytest-asyncio` | 测试 |
| `ruff` | 格式化 + Lint |

### 禁止使用的包
- `flask` / `django` / `fastapi`（WebUI 阶段尚未实现，不可提前引入）
- `sqlalchemy` / `tortoise-orm`（存储层需手写，不引入 ORM）
- `black` / `flake8`（使用 ruff）

---

## 编码规约

1. **注释**: 所有业务代码必须含详细中文注释，遵循 3W1H 框架（What / Why / Where / How）
2. **异常处理**: 不可出现裸 `except:`；LLM 调用须有超时 + 重试机制
3. **导入顺序**: 标准库 → 第三方 → 项目内部（三段式，每段空行分隔）
4. **日志**: 使用 logging 模块输出 JSON 格式结构化日志
5. **配置**: 敏感信息放 `.env`，全局配置放 `config.yaml`，日志配置放 `config/logging.yaml`
6. **测试**: 每新增核心功能必须编写对应的 pytest 测试
7. **用户隔离**: 所有数据操作必须基于当前用户 ID 进行过滤

---

## 测试约定

1. **pytest-asyncio 模式**: 采用 `auto` 模式，在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 中配置 `asyncio_mode = "auto"`
2. **存储层测试**: 使用 `tmp_path` fixture 生成临时 SQLite 文件，不使用 `:memory:`
3. **模块对应**: 每个 `core/` 模块对应一个 `test_*.py`，测试时 mock 掉底层 storage 依赖

---

## 关键约定速查

| 约定 | 规则 |
|------|------|
| 项目名 | `langchain-chat` |
| 主入口 | `src/main.py` |
| 配置加载 | `src/core/config_manager.py` |
| 存储切换 | `config.yaml` → `storage.type` |
| 内置预设 | `config/presets.yaml` |
| 导出目录 | `data/users/{username}/exports/` |
| 会话标题 | 首轮用户消息前 30 字符 |
| 模型切换 | 会话内可中途切换，保留历史上下文 |
| UI 扩展 | 新增 UI 需实现 `ui_protocol.py` 中的接口 |
| H2 多模型对比 | 基础功能 A-G 完成后作为独立任务实现 |
| LLM 重试 | config.yaml → llm.timeout / llm.max_retries |
| 后期预留 | H1/H3/H4/H5 只定义接口签名，不实现逻辑 |

---

## 工作流与追溯规范

### 1. 需求追溯
- 每个模块/函数的实现，必须能对应回需求说明文档的具体编号（如 A1、C6、H2）
- 核心文件（chat_engine.py、session_manager.py 等）顶部注释需列出本文件覆盖的需求编号
  示例：# 覆盖需求: A1(多轮对话) A2(流式输出) A5(会话内模型切换)

### 2. Workflow Log（开发过程日志）
- 位置: docs/workflow_log.md
- 每完成一个开发步骤（对应一次 commit），追加一条记录，格式:
  ## [步骤编号] 模块名 — YYYY-MM-DD
  - 对应需求: xxx
  - 设计要点: (Plan 阶段的关键决策，如字段设计、异常处理策略)
  - 变更文件: xxx
  - 对应 commit: &lt;hash&gt;
  - 对应 tag: v0.x-xxx（如有）
  - 遗留问题/待办: xxx（如有）
- 目的: 让人（不只是 AI）之后能追溯"为什么这么设计"，不用重新翻对话记录

### 3. Git Commit Flow
- 采用 Conventional Commits 规范:
  feat: 新功能    fix: 修复    docs: 文档    test: 测试
  refactor: 重构  chore: 杂项  style: 格式调整
- 提交粒度: 一个逻辑步骤一次 commit，不跨层合并提交
  （如 models 和 storage 分开提交，不要一次性提交多层）
- 每个里程碑（完成一层）打 tag，格式: v0.&lt;序号&gt;-&lt;层名&gt;
  如 v0.1-agents-md-revised、v0.2-models、v0.3-storage
- commit message 第二行起可选写明对应需求编号和 workflow_log 条目位置

### 4. 工程规范补充
- 每次 Build 前必须先过 Plan 阶段（设计方案 + 人工确认），不允许跳过直接写代码
- 每层完成后运行 ruff check + pytest，确保通过才允许 commit
- CHANGELOG.md 可选，若维护则每次 tag 时同步更新
