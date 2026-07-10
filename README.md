# langchain-chat

基于 LangChain 的多轮对话系统 + 教学项目。全链路异步（`asyncio`），分层架构，当前 TUI 交互，预留 WebUI 扩展。

---

## 功能清单

### A — 对话核心（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| A1 | 多轮对话（历史上下文保持） | ✅ |
| A2 | 流式输出（逐 token 渲染） | ✅ |
| A3 | 全异步（全链路 async/await） | ✅ |
| A4 | 可配置 LLM 后端（.env → API_BASE_URL / API_KEY / MODEL_NAME） | ✅ |
| A5 | 会话内中途切换模型 | ✅ |

### B — 用户体系（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| B1 | 创建用户 | ✅ |
| B2 | 用户切换 | ✅ |
| B3 | 删除用户 | ✅ |
| B4 | 用户隔离（数据按用户隔离 + 用户级配置） | ✅ |

### C — 会话管理（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| C1 | 创建会话 | ✅ |
| C2 | 加载历史会话 | ✅ |
| C3 | 列出会话 | ✅ |
| C4 | 重命名会话 | ✅ |
| C5 | 删除会话 | ✅ |
| C6 | 消息自动持久化 | ✅ |
| C7 | 会话标题自动生成（首条 human 消息前 30 字符） | ✅ |

### D — 预设系统（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| D1 | 系统内置预设（config/presets.yaml 加载） | ✅ |
| D2 | 用户自定义预设 CRUD | ✅ |
| D3 | 预设选择（创建会话时选择预设） | ✅ |
| D4 | 预设管理菜单接口 | ✅ |

### E — 搜索与统计（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| E1 | 全文搜索消息 | ✅ |
| E2 | Token 用量统计 | ✅ |

### F — 导出（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| F1 | Markdown 格式导出 | ✅ |
| F2 | 导出到 `data/users/{username}/exports/` | ✅ |

### G — 工程基础（完整实现）
| 编号 | 功能 | 状态 |
|------|------|------|
| G1 | 超时与重试（`config.yaml → llm.timeout / max_retries`） | ✅ |
| G2 | JSON 结构化日志 | ✅ |
| G3 | 配置管理（ConfigManager 统一建模 .env + config.yaml） | ✅ |

### H — 扩展能力
| 编号 | 功能 | 状态 |
|------|------|------|
| H1 | UI 协议接口（`src/interface/ui_protocol.py`） | ✅ 完整定义 |
| H2 | 多模型对比（`src/core/comparator.py`） | ✅ 真实实现，并发调用多个模型 |
| H3 | 图像理解协议 | ⚠️ 仅接口占位（`raise NotImplementedError`） |
| H4 | 语音协议 | ⚠️ 仅接口占位（`raise NotImplementedError`） |
| H5 | 工具调用协议 | ⚠️ 仅接口占位（`raise NotImplementedError`） |

---

## 快速开始

### 环境要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)（推荐）或 pip

### 安装

```bash
cd langchain-chat
uv sync
```

### 配置

复制 `.env.example` 为 `.env`，填入必要字段：

| 字段 | 说明 |
|------|------|
| `API_BASE_URL` | OpenAI 兼容 API 地址（如 `https://api.openai.com/v1`） |
| `API_KEY` | API 密钥 |
| `MODEL_NAME` | 默认模型名（如 `gpt-4o`） |

### 启动

```bash
uv run python -m src.main
```

> 为什么用 `python -m src.main` 而不是 `python src/main.py`？
>
> `-m` 方式能正确设置 Python 包搜索路径，避免相对导入失败。
> `main.py` 顶部有兼容处理（`sys.path.insert(0, ...)`）使两种调用方式都能工作，
> 但标准用法推荐 `-m`。详见 `src/main.py:3-5`。

---

## 项目结构

```
langchain-chat/
├── config/                  # 配置文件（presets.yaml, logging.yaml）
├── src/
│   ├── models/              # 数据模型层（Pydantic）
│   ├── storage/             # 存储层（抽象基类 + 实现）
│   ├── core/                # 业务层（ChatEngine, Manager 等）
│   ├── interface/           # UI 接口定义层（Protocol）
│   └── ui/                  # UI 实现层
│       ├── tui/             # 当前终端界面
│       └── web/             # WebUI 预留
├── tests/                   # 单元测试（pytest + pytest-asyncio）
├── docs/                    # 文档
├── .env                     # 敏感配置（gitignore）
├── pyproject.toml
└── AGENTS.md                # 完整目录结构与分层规约
```

### 分层依赖（单向）

```
models → storage → core → interface → ui
```

- **核心约束**: `core/` 不引用 `ui/`，通过 `interface/` 解耦
- **存储可插拔**: 通过 `StorageFactory` 切换后端

---

## 已知限制

1. **H3/H4/H5** — 图像/语音/工具调用只有接口协议占位（`src/interface/capability_protocols.py`），无具体业务实现，调用会抛出 `NotImplementedError`
2. **MySQL / File 存储后端** — `StorageFactory` 目前只注册了 `sqlite`；`mysql_backend.py` 和 `file_backend.py` 尚未创建，是纯计划项
3. **update_user / update_preset 异常语义** — 对不存在的 `user.id` / `preset.id`，当前通过 `assert result is not None` 触发 `AssertionError`，而非抛出清晰的 `ValueError`。不影响正常业务流程，但属于工程欠账
4. **单机运行** — 当前仅支持本地 SQLite 存储，无分布式部署能力
5. **无身份验证** — 用户切换仅凭用户名，无密码/令牌机制（适合教学/个人使用，不适合生产）

---

## 开发工作流

本项目遵循 **Plan → Build → Test → Commit** 的完整开发流程：

1. **AGENTS.md** — 记录工程规范、目录结构、命名约定、技术栈约束，供 AI Agent 和人类开发者共同遵守
2. **docs/workflow_log.md** — 每步开发的关键决策追溯（为什么这么设计，而不是只记录做了什么）
3. **Git tags** — 每个里程碑对应一个 tag（`v0.1` ~ `v0.19`），方便回退和追溯
4. **自动化** — 每步提交前运行 `ruff check` + `pytest`，确保代码质量和测试通过

当前测试覆盖：**145 项**（`pytest`），覆盖全部核心模块。
