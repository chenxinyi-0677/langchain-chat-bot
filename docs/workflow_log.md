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
