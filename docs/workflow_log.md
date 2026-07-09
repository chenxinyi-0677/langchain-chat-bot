# 工作流日志

本文件记录 langchain-chat 项目的开发步骤及关键决策，确保每步可追溯。

---

## v0.2-models — 数据模型层实现

**日期**: 2026-07-09

### 范围
实现 `src/models/schemas.py`，定义五个核心实体的 Pydantic 模型。

### 关键决策
1. **Session.title = Optional[str] = None**：创建会话时标题未知，由 C7 自动生成逻辑后续填充
2. **username 正则校验 `^[a-zA-Z0-9_-]+$`**：避免特殊字符污染导出路径 `data/users/{username}/exports/`
3. **Preset.description = Optional[str] = None**：部分预设无需详细描述
4. **created_at / updated_at 统一 UTC**：通过 `datetime.now(timezone.utc)` 生成

### 文件清单
| 文件 | 说明 |
|------|------|
| `src/__init__.py` | 源码包标记 |
| `src/models/__init__.py` | models 包标记 |
| `src/models/schemas.py` | 5 个 Pydantic 模型（User/Session/Message/Preset/UserConfig） |
| `tests/__init__.py` | 测试包标记 |
| `tests/test_models.py` | 模型层测试骨架（fixture + 空测试类） |
| `docs/workflow_log.md` | 本文件 |

### 前置依赖
- AGENTS.md 已定义技术栈约束和编码规约

---

## v0.1-agents-md-revised — AGENTS.md 初版

**日期**: 2026-07-09

### 范围
基于需求说明文档生成 AGENTS.md，定义目录结构、分层架构、命名规范、技术栈约束。

### 关键决策
1. **依赖版本锁定**：langchain==1.3.11, langchain-core==1.4.8, langchain-openai==1.3.2（均经 PyPI 核实）
2. **H2 定位**：从后期预留拆出，基础功能 A-G 完成后作为独立任务实现
3. **测试约定**：pytest-asyncio auto 模式 + tmp_path SQLite + 模块对应 mock

### 文件清单
| 文件 | 说明 |
|------|------|
| `AGENTS.md` | 项目规范文档 |
