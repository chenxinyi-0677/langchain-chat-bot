# Workflow Log — 开发过程日志

## 目的

记录 langchain-chat 项目每个开发步骤的关键决策、变更范围和对应 commit，
确保人（不限于 AI）可以追溯"为什么这么设计"，无需重新翻阅原始对话记录。

## 维护者

所有参与开发的 AI Agent 和人类开发者。每完成一个逻辑步骤（对应一次 commit），
按以下格式追加一条记录。

## 追加时机

- 每次 commit 前，将本步骤的决策要点记录在此文件
- 与代码变更一同提交，确保日志与 commit 历史一一对应

---

## [步骤0] 需求文档评审与 AGENTS.md 初版 — 2026-07-09

- **对应需求**: 全部（项目初始化）
- **设计要点**:
  - H2（多模型并行对比）从后期预留拆出，基础功能 A-G 完成后作为独立任务实现
  - 测试约定：pytest-asyncio auto 模式、tmp_path SQLite、模块对应 + mock
  - LLM 重试配置位置：`config.yaml → llm.timeout / llm.max_retries`
  - 三个核心依赖版本经 PyPI 核实锁定：langchain==1.3.11、langchain-core==1.4.8、langchain-openai==1.3.2
- **变更文件**: `AGENTS.md`
- **对应 commit**: `33aa5ca`
- **对应 tag**: `v0.1-agents-md-revised`
- **遗留问题/待办**: 无

---

## [步骤1] 数据模型层 — 2026-07-09

- **对应需求**: 需求文档 4.3 节（数据实体设计）
- **设计要点**:
  - Session.title 为 `Optional[str] = None`，创建时未知，由 C7 自动生成
  - username 增加正则校验 `^[a-zA-Z0-9_-]+$`，避免特殊字符污染 F2 导出路径
  - Preset.description 改为 `Optional[str] = None`
  - created_at / updated_at 统一使用 `datetime.now(timezone.utc)` 生成
  - 五个实体均设计 Create 变体（不含 id/时间戳）+ 完整模型两套
- **变更文件**:
  - `src/models/schemas.py`
  - `tests/test_models.py`
  - `src/__init__.py` / `src/models/__init__.py` / `tests/__init__.py`
- **对应 commit**: `9ccb5fd`
- **对应 tag**: `v0.2-models`
- **遗留问题/待办**: 已在本步骤（[步骤2]）补充真实断言并全部通过

---

## [步骤2] 存储层 — 2026-07-09

- **对应需求**: 4.1（可插拔后端设计）、4.2（工厂模式）、4.3（数据实体 DDL）
- **设计要点**:
  - StorageBackend 抽象基类定义 5 组实体的统一异步 CRUD 接口
  - StorageFactory 根据 config.yaml 的 storage.type 创建对应后端实例
  - SQLite DDL 所有外键加 ON DELETE CASCADE（配合 PRAGMA foreign_keys = ON）
  - 时间戳存 ISO 8601 文本，Python 侧 Pydantic 序列化/反序列化
  - Session.title 应用层兜底 `"未命名会话"`（create_session 内转换）
  - 补全 test_models.py 真实断言（40 项全部通过）
- **遗留设计决策（记录给 session_manager 参考）**:
  - `title` 的占位符字符串无法用于判断"是否需要自动生成标题"
  - C7 触发逻辑应基于"是否为该 session 的第一条 human 消息"或显式状态标记，
    **不要**通过 `title == "未命名会话"` 判断，避免用户手动改为同名标题时误判
- **变更文件**:
  - `src/storage/base.py`（新建）
  - `src/storage/__init__.py`（新建）
  - `src/storage/factory.py`（新建）
  - `src/storage/sqlite_backend.py`（新建）
  - `src/models/schemas.py`（Message.role → Literal 类型限定）
  - `tests/conftest.py`（新建：tmp_sqlite_backend fixture）
  - `tests/test_storage.py`（新建：28 项集成测试）
  - `tests/test_models.py`（填充真实断言 + 修正 3 项测试）
  - `pyproject.toml`（新建：项目元数据 + 依赖声明 + pytest/ruff 配置）
  - `.venv/`（依赖安装环境）
- **对应 tag**: `v0.3-storage`（commit `e583e95`）

---

## [步骤3] 会话管理层 — 2026-07-09

- **对应需求**: C1（新建会话）、C2（加载历史）、C3（会话列表）、C4（重命名）、C5（删除会话）、C6（自动保存）、C7（标题自动生成）、E2（Token 统计）、B4（用户隔离）
- **设计要点**:
  - `_title_generated` 内存缓存标记：create_session 置 False，load_session 查一次库初始化，避免每次 add_user_message 全表扫描
  - C7 触发条件基于"此 session 在此之前是否有 human 消息"，不比较 `title == "未命名会话"`
  - 复用 `backend.update_session(session)` 持久化标题变更 + token 累计，不新增专用方法
  - delete_session 同时重置 `_current_session = None` + `_title_generated = False`
  - 所有操作先校验会话归属（B4 用户隔离），非归属用户抛出 ValueError
- **变更文件**:
  - `src/core/__init__.py`（新建）
  - `src/core/session_manager.py`（新建）
  - `tests/conftest.py`（新增 test_user fixture）
  - `tests/test_session_manager.py`（新建，28 项测试）
- **对应 tag**: `v0.4-session-manager`

---

## [步骤4] 用户管理层 — 2026-07-10

- **对应需求**: B1（创建用户）、B2（获取用户/切换前置）、B3（删除用户）、B4（用户隔离）
- **设计要点**:
  - UserManager 不缓存当前用户状态，每次操作直通存储层
  - "当前用户"概念归属应用层（TUI app.py），切换用户时由应用层重建 SessionManager
  - 唯一性校验策略：DB UNIQUE 约束兜底（方案 A），Manager 层额外做正则校验 `^[a-zA-Z0-9_-]+$`
  - 新增 `update_user` 方法暴露给用户设置功能修改 default_model / default_preset_id
  - 补上 `sqlite_backend.py` 的 `update_user` IntegrityError → ValueError 转换，与 `create_user` 保持一致
  - 删除用户：先查存在性 + 防御性 `ValueError`，级联删除由 ON DELETE CASCADE 处理
- **变更文件**:
  - `src/core/user_manager.py`（新建，~100 行）
  - `tests/test_user_manager.py`（新建，11 项测试）
  - `src/storage/sqlite_backend.py`（update_user 加 IntegrityError 捕获）
- **待办**:
  - `sqlite_backend.py:update_user` 对不存在的 user.id 用 `assert` 做业务校验，应改为 `raise ValueError`（当前静默通过 UPDATE 0 行后 assert 失败，语义不清）
- **对应 commit**: `c578db6`
- **对应 tag**: `v0.5-user-manager`

---

## [步骤5] 预设管理层 — 2026-07-10

- **对应需求**: D1（系统内置预设）、D2（自定义预设 CRUD）、D3（预设选择）、D4（管理菜单接口）
- **设计要点**:
  - 三步校验（update/delete 共用）：存在性 → 非内置 → 归属当前用户
  - 内置预设（is_builtin=True）全员共享，Manager 层拦截编辑/删除请求
  - get_preset 不校验归属，任何人可按 preset_id 获取任意预设（用于 D3 会话创建时加载预设内容）
  - PresetManager 绑定 user_id，create_preset 自动绑定当前用户
- **变更文件**:
  - `src/core/preset_manager.py`（新建，~140 行）
  - `tests/test_preset_manager.py`（新建，17 项测试，6 个测试类）
- **待办**:
  - `sqlite_backend.py:update_preset` 同样存在 `assert result is not None` 问题（同 update_user），应改为 `raise ValueError`
- **对应 commit**: `30a2a4b`
- **对应 tag**: `v0.6-preset-manager`

---

## [步骤6] 配置管理层 — 2026-07-10

- **对应需求**: A4（.env → API_BASE_URL/API_KEY/MODEL_NAME）、G1（config.yaml → llm.timeout/max_retries）、G3（区分两个来源统一建模）
- **设计要点**:
  - 统一管理 .env（pydantic-settings BaseSettings）和 config.yaml（PyYAML → Pydantic），对外暴露 `AppConfig` 单一模型
  - storage 配置也归 ConfigManager 管理（StorageFactory 依赖 config dict）
  - `load()` 为同步方法：仅涉及本地文件读取 + yaml.parse，无阻塞 IO 等待，加 async 徒增开销
  - 首次创建 `config.yaml` 和 `.env.example` 配置文件
- **变更文件**:
  - `src/core/config_manager.py`（新建，~115 行，含 5 个配置模型 + ConfigManager）
  - `tests/test_config_manager.py`（新建，13 项测试，4 个测试类）
  - `config.yaml`（新建，默认配置模板）
  - `.env.example`（新建，环境变量模板，.env 本身不提交）
- **对应 commit**: `51ca994`
- **对应 tag**: `v0.7-config-manager`

---

## [步骤7] 对话引擎 — 2026-07-10

- **对应需求**: A1（多轮对话）、A2（流式输出）、A3（全异步）、A4（可配置LLM后端）、A5（会话内切换模型）、G1（超时+重试）、E2（Token统计）
- **设计要点**:
  - Memory 策略：手动将 SessionManager.get_messages() 转为 LangChain 消息格式（langchain.memory 在 1.3.11 中不存在），每次 chat() 调用时重新转换，A5 切换模型不受影响
  - Token 统计：ChatOpenAI(stream_usage=True) → astream 最后一条 chunk 的 usage_metadata
  - 超时+重试：直接使用 ChatOpenAI 内置的 timeout / max_retries 参数
  - ChatEngine 与 SessionManager 关系：依赖注入，ChatEngine 构造时接收 SessionManager 实例
  - chat() 为 async generator，一次调用完成保存用户消息 → 拉取历史 → 调 LLM → yield 逐 token → 提取 usage → 保存 AI 回复
  - SessionManager 新增 `update_model` 公开方法（参考 rename_session 模式），ChatEngine 不再直接访问 _backend
  - `_build_llm()` 从 `session_mgr.current_session.model_name` 读取模型名（支持 A5）
  - 构造函数不持有 backend，全部通过 session_mgr 转发
- **变更文件**:
  - `src/core/chat_engine.py`（新建，~150 行）
  - `tests/test_chat_engine.py`（新建，9 项测试）
  - `src/core/session_manager.py`（新增 update_model 方法 + 3 项测试）
- **对应 commit**: `95590b3`
- **对应 tag**: `v0.8-chat-engine`

---

## [步骤8] UI 协议接口 — 2026-07-10

- **对应需求**: H1（UI 协议接口定义）
- **设计要点**:
  - 使用 `typing.Protocol` 而非 ABC——实现方无需继承，结构匹配即满足
  - 覆盖 5 个功能域：User / Session / Chat / Preset / Token
  - switch_user 要求实现方原子性重建 SessionManager + ChatEngine（避免二者指向不同用户）
  - 协议只定义接口，不实现逻辑（符合 AGENTS.md "H1 只定义接口签名"）
  - TUIApp 隐式实现此协议，通过委托持有各 Manager 实例
- **变更文件**:
  - `src/interface/__init__.py`（新建）
  - `src/interface/ui_protocol.py`（新建，~140 行，17 个方法/属性）
- **对应 commit**: `7cb7438`
- **对应 tag**: `v0.9-ui-protocol`

---

## [步骤9] TUI 骨架 — 2026-07-10

- **对应需求**: B1（创建用户）、B2（切换用户）、C1（新建会话）、D3（预设选择）、H1（UI 协议骨架实现）
- **设计要点**:
  - 登录流程：首次启动自动走创建，已有用户时选择或输入新用户名
  - switch_user 原子性重建 SessionManager + PresetManager + ChatEngine
  - chat 命令前置检查：无当前会话时先走"输入模型名 → 选预设 → create_session"流程
  - 当前骨架使用简单 print/input 占位，后续用 rich + prompt_toolkit 美化
- **变更文件**:
  - `src/main.py`（新建，启动流程：ConfigManager → StorageFactory → init_db → TUIApp）
  - `src/ui/__init__.py`（新建）
  - `src/ui/tui/__init__.py`（新建）
  - `src/ui/tui/app.py`（新建，~220 行，登录/主循环/chat/sessions/presets/switch）
- **对应 commit**: `6a11f2b`
- **对应 tag**: `v0.10-tui-skeleton`

---

## [步骤10] 冒烟测试与环境修复 — 2026-07-10

- **对应需求**: 全部（端到端验证）
- **发现的三个环境问题**:

  ### 问题1: SQLite 父目录未自动创建
  - **现象**: `sqlite3.OperationalError: unable to open database file`
  - **根因**: `init_db()` 直接用 `aiosqlite.connect(self._path)`，SQLite 只创建库文件本身，不自动创建父目录 `data/sqlite/`
  - **修复**: `init_db()` 中 `connect()` 前插入 `Path(self._path).parent.mkdir(parents=True, exist_ok=True)`
  - **回归测试**: `TestInitDb::test_init_db_creates_parent_directory`
  - **对应 commit**: `ea3ae5c`

  ### 问题2: ConfigManager 路径依赖 cwd
  - **现象**: 从非项目根目录启动时，`from src.core.config_manager import ...` 正常（已解决），但 `.env` / `config.yaml` 还是基于 cwd 的相对路径，找不到文件 → `api_key = ""` → ChatOpenAI 报 Missing credentials
  - **根因**: `ConfigManager.__init__` 默认参数 `env_file = ".env"` 为相对路径，取决于运行时 cwd
  - **修复**: 在模块级计算 `_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent`，默认路径基于项目根目录；`load()` 提前检测 `.env` 是否存在，不存在则抛 `FileNotFoundError`（替代 ChatOpenAI 的 Missing credentials）
  - **测试调整**: `test_load_defaults_when_no_files` → `test_load_defaults_when_no_yaml`（需最小 `.env`）；新增 `test_load_missing_dotenv_raises`
  - **对应 commit**: `fd781c2`

  ### 问题3: `python src/main.py` 报 ModuleNotFoundError
  - **现象**: `ModuleNotFoundError: No module named 'src'`
  - **根因**: 直接运行脚本时 Python 将脚本所在目录（`src/`）加入 `sys.path`，而非项目根目录，`from src.xxx import` 找不到包
  - **修复**: `main.py` 顶部加入 `if __name__ == "__main__" and not __package__: sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`，同时兼容两种启动方式
  - **标准化**: 推荐 `uv run python -m src.main` 作为唯一标准启动命令（已在 README.md 中写明），`-m` 方式是 Python 社区推荐做法
  - **对应 commit**: `e6e5d1a`

- **变更文件**:
  - `README.md`（新建：启动命令 + 首次使用 + 测试说明）
  - `docs/workflow_log.md`（本条记录）
  - `src/storage/sqlite_backend.py`（init_db 自动建目录）
  - `tests/test_storage.py`（回归测试 + Path 导入）
  - `src/core/config_manager.py`（项目根路径解析 + 缺失检测）
  - `tests/test_config_manager.py`（测试隔离 + 新增测项）
  - `src/main.py`（sys.path 兼容）
- **对应 commit**: `e6e5d1a`（最后一步 docs 类提交）
- **遗留问题/待办**: 无（121 项单元测试 + 2 项新测试全部通过）

---

## [步骤11] E1 对话搜索 — 2026-07-10

- **对应需求**: E1（在当前用户的历史会话中按关键词搜索消息）
- **设计要点**:
  - 存储层 `search_messages` 在 v0.3 已实现（base.py 抽象 + sqlite_backend.py SQL JOIN+LIKE），无需重复造轮
  - 不新建 SearchManager，直接加到 SessionManager——它已有 `_backend` + `_user_id`，纯透传
  - SessionManager.search_messages() 只有一行 `return await self._backend.search_messages(self._user_id, keyword)`
  - UIProtocol 新增 `search_messages` 方法签名
  - TUI 侧新增 `search` 子命令，结果按会话分组展示，消息内容截断至 80 字符
- **变更文件**:
  - `src/core/session_manager.py`（新增 search_messages 方法 + 更新覆盖需求注释）
  - `src/interface/ui_protocol.py`（新增 search_messages 签名）
  - `src/ui/tui/app.py`（新增 search 命令 + 结果展示）
  - `tests/test_session_manager.py`（新增 TestSearchMessages，2 项 mock 测试）
- **对应 tag**: `v0.11-search`

---

## [步骤12] F1/F2 对话导出 — 2026-07-10

- **对应需求**: F1（导出 Markdown）、F2（导出到 data/users/{username}/exports/）
- **设计要点**:
  - 新建 `src/core/exporter.py` 单独模块，不塞进 SessionManager（涉及文件 I/O + Markdown 格式化 + 文件名清理，非透传）
  - 时间戳处理：数据库存 UTC，导出时 `.astimezone()` 转本地时区后 `strftime` 输出
  - Token 统计来源区分：标题区读 `Session.total_prompt_tokens / total_completion_tokens`（会话累计），每条 AI 消息末尾读 `Message.prompt_tokens / completion_tokens`（单条明细）
  - 文件名清理：`re.sub(r'[\\/:*?"<>|]', '_', title)` 后 `.strip()`，空标题兜底为"未命名会话"
  - 导出目录自动创建 `mkdir(parents=True, exist_ok=True)`（吸取 init_db 教训）
  - Exporter 构造函数注入 backend + user_id + username；归属校验：`session.user_id != self._user_id`
- **变更文件**:
  - `src/core/exporter.py`（新建，Exporter 类）
  - `src/interface/ui_protocol.py`（新增 export_session 签名）
  - `src/ui/tui/app.py`（新增 export 子命令 + Exporter 实例化）
  - `tests/test_exporter.py`（新建，11 项测试：文件名清理 ×4、格式化 ×3、集成 ×4）
- **对应 tag**: `v0.12-exporter`

---

## [步骤13] G2 结构化日志 — 2026-07-10

- **对应需求**: G2（JSON 格式结构化日志，config/logging.yaml 独立管理）
- **设计要点**:
  - 标准库 `logging` + 自定义 `JSONFormatter`，不引入第三方日志库
  - JSONFormatter 输出单行 JSON：`timestamp` / `level` / `logger` / `message` + `extra` 自动合并
  - `extra` 参数传入的自定义属性（如 `user_id`、`session_id`）自动出现在 JSON 中（通过过滤 `_STANDARD_RECORD_KEYS` 实现）
  - 日志配置独立文件 `config/logging.yaml`，支持 console + file 双 handler，file 使用 RotatingFileHandler（10MB 轮转）
  - `setup_logging()` 在读取 `logging.yaml` 前先 `mkdir(parents=True, exist_ok=True)` 创建 `data/logs/`，避免 RotatingFileHandler 踩 SQLite 同款坑
  - 埋点范围（只覆盖关键操作 + 错误）：
    - UserManager: create_user (INFO) / delete_user (INFO + WARNING)
    - SessionManager: create_session (INFO) / delete_session (INFO)
    - PresetManager: create_preset (INFO) / delete_preset (INFO)
    - ChatEngine: chat 启动 (INFO) / 完成 (INFO, 含 token) / LLM 失败 (ERROR)
    - Exporter: export (INFO)
- **变更文件**:
  - `config/logging.yaml`（新建，日志配置）
  - `src/core/logger.py`（新建，JSONFormatter + setup_logging）
  - `src/main.py`（启动时调用 setup_logging）
  - `src/core/user_manager.py`（加日志埋点）
  - `src/core/session_manager.py`（加日志埋点）
  - `src/core/preset_manager.py`（加日志埋点）
  - `src/core/chat_engine.py`（加日志埋点）
  - `src/core/exporter.py`（加日志埋点）
  - `tests/test_logger.py`（新建，4 项测试：JSON 结构 + extra 字段 + 目录创建 + 配置回退）
- **对应 tag**: `v0.13-logging`

---

## [步骤14] H2 多模型并行对比 — 2026-07-10

- **对应需求**: H2（多模型并行对比）
- **设计要点**:
  - 新建 `src/core/comparator.py`，独立于 ChatEngine（不需 session，不需持久化）
  - `ModelResult` 数据类：model_name, response, prompt_tokens, completion_tokens, error（可选）
  - `Comparator._call_single()` 内部 try/except 捕获异常转 `ModelResult(error=...)`，不向外抛
  - `compare(prompt, model_names)` 用 `asyncio.gather(*tasks)` 并发收集所有结果——因每个协程都返回 ModelResult，gather 不会见到异常，一个模型失败不影响其他
  - 结果不落库（H2 是 1 对 N，现有 Message 模型一对多不兼容）
  - TUI 侧新增 compare 子命令：输入 prompt + 逗号分隔模型名，等全部返回后逐个展示（`===` 分隔线隔开每个模型的输出块）
- **变更文件**:
  - `src/core/comparator.py`（新建，Comparator + ModelResult）
  - `src/interface/ui_protocol.py`（新增 compare_models 签名）
  - `src/ui/tui/app.py`（新增 compare 子命令 + Comparator 实例化）
  - `tests/test_comparator.py`（新建，5 项测试：ModelResult ×2、并发 ×2、空列表）
- **对应 tag**: `v0.15-h2`

---

## [步骤15] TUI 美化 — 2026-07-10

- **对应需求**: 全部（UI 层视觉优化）
- **设计要点**:
  - 主循环骨架不动，仅替换 `print`/`input` 为 rich/prompt_toolkit
  - `widgets.py`：集中管理 Console 实例、`get_command_prompt()`（命令补全 + FileHistory）、`get_input()`
  - `chat_view.py`：用户消息蓝色 Panel 瞬间渲染，AI 回复用 `rich.live.Live` 逐 token 刷新绿色 Panel 内容，保留 A2 流式视觉效果
  - `menu_view.py`：`rich.Table` 渲染会话/预设列表，`rich.Panel` 渲染搜索结果和模型对比结果
  - `app.py`：所有 `input()` → `get_command_prompt()` / `get_input()`，所有 `print()` → `show_message()` / `show_success()` / `show_error()`
- **变更文件**:
  - `src/ui/tui/app.py`（重写：迁移所有 print/input）
  - `src/ui/tui/widgets.py`（重写：prompt_toolkit + rich 组件）
  - `src/ui/tui/chat_view.py`（重写：Live 流式 Panel）
  - `src/ui/tui/menu_view.py`（重写：Table + Panel 渲染器）
- **对应 tag**: `v0.16-tui-polish`

---

## [步骤16] 修复异步架构 Bug — 2026-07-10

- **对应需求**: 全部（全链路异步约束修复）
- **背景**: `widgets.py` 使用同步 `prompt_toolkit.shortcuts.prompt()`，该函数内部调用 `asyncio.run()`，与 `main.py` 已运行的事件循环冲突，导致 `asyncio.run() cannot be called from a running event loop` 崩溃
- **修复内容**:
  - `widgets.py`: 三个输入函数改为 `async def`，使用 `PromptSession.prompt_async()` 替代同步 `prompt()`
  - `widgets.py`: `_cmd_session` / `_input_session` 改为惰性初始化（`None` → 首次调用时创建），避免模块导入时因无终端环境崩溃
  - `app.py`: 全部 13 处 `get_input()`, `get_command_prompt()`, `get_input_with_default()` 调用加 `await`
  - `chat_view.py` / `menu_view.py`: 审查确认无同步/异步混用隐患（纯 `rich` API，不涉及事件循环）
- **变更文件**: `src/ui/tui/widgets.py`, `src/ui/tui/app.py`
- **对应 tag**: `v0.17-async-fix`

---

## [步骤17] 修复 Live 流式渲染 Bug — 2026-07-10

- **对应需求**: A2（流式输出视觉效果）
- **背景**: `show_ai_stream` 的 `Live` 使用存在三个 bug：未捕获 `live` 实例 → 无法调用 `live.update()`；`panel.renderable = ai_text` 是空赋值（同一对象）；全依赖 auto_refresh 导致终端内每次刷新打印新 Panel 而非原地覆盖
- **修复**:
  - `with Live(...) as live:` 捕获实例
  - 循环内调用 `live.update(panel)` 触发立即原地重绘
  - 移除无意义的 `panel.renderable = ai_text`
- **变更文件**: `src/ui/tui/chat_view.py`
- **对应 tag**: `v0.18-live-fix`

---

## [步骤18] 修复 Live + 日志终端冲突 — 2026-07-10

- **对应需求**: A2 / G2（流式输出视觉效果 + 日志不干扰 UI）
- **背景**: `logging.StreamHandler` 向 stdout 写 JSON 日志行，与 `rich.live.Live` 共用同一终端流且无协调，导致日志行出现在 Panel 边框内。`chat_view.py` 的 Live 用法本身已正确（`with Live() as live:` + `live.update()` + 无多余 `console.print`）
- **修复**:
  - `config/logging.yaml`: 移除 `console: StreamHandler`；`src` logger 只保留 `file` handler；root logger 不再设 handler
  - `.gitignore`: 修复 `.cmd_history` 规则（之前被 `#` 注释吞掉）
- **变更文件**: `config/logging.yaml`, `.gitignore`
- **对应 tag**: `v0.19-log-conflict-fix`

---

## [步骤19] D1 内置预设：创建 presets.yaml + 启动同步逻辑 — 2026-07-10

- **对应需求**: D1（系统内置预设完整落地）
- **背景**: D1 此前只有数据模型和查询接口，`config/presets.yaml` 从未创建，启动时也无同步逻辑，导致数据库 `presets` 表始终为空，"暂无内置预设"是必然结果
- **修正**:
  - `config/presets.yaml`: 创建文件，定义 2 个内置预设（`translator` / `code_expert`），每条带稳定 `slug` 标识
  - `Preset` 模型新增 `slug: Optional[str]` 字段，仅内置预设使用，用户自定义预设为 None
  - `PresetManager.sync_builtin_presets()`: 静态方法，以 slug 为匹配键执行全量同步（INSERT + UPDATE + DELETE），YAML 是内置预设的唯一数据源
  - `sqlite_backend.py`: DDL 新增 `slug TEXT` 列 + `_migrate()` 自动添加；`delete_preset` 先 `UPDATE sessions SET preset_id=NULL` 再 DELETE，避免孤儿引用
  - `main.py`: `init_db()` 后调用 `PresetManager.sync_builtin_presets(backend)`
  - `sqlite_backend.py` 注释：修正"所有外键加 ON DELETE CASCADE"的不准确表述，如实列出各字段的外键行为
  - `StorageBackend` 基类新增 `get_preset_by_slug` 抽象方法
- **同步边界**（记录备忘）:
  - 以 slug 匹配，不是 name。改名只触发 UPDATE，不会 DELETE 重建
  - YAML 删除某条时，DB 中对应记录会被 DELETE（sessions 引用已提前清空）
  - 幂等：多次重启不重复 INSERT
- **变更文件**: `config/presets.yaml`, `src/models/schemas.py`, `src/storage/base.py`, `src/storage/sqlite_backend.py`, `src/core/preset_manager.py`, `src/main.py`
- **对应 tag**: `v0.20-builtin-presets`
