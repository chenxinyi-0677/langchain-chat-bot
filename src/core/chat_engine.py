"""
对话引擎 —— ChatEngine

【What】
多轮对话核心：接收用户输入 → 组装历史上下文 → 调用 LLM 流式输出 → 持久化。

【覆盖需求】
A1(多轮对话)  A2(流式输出)  A3(全异步)  A4(可配置LLM后端)  A5(会话内切换模型)
G1(超时 + 重试)  E2(Token 统计)

【Why】
- ChatEngine 是 core/ 层对外暴露的核心组件，TUI 直接调用 chat() 完成一轮对话
- 历史消息转换 + LLM 调用 + 结果持久化在一个 async generator 中闭环，
  TUI 无需协调多个 Manager

【Where】
- TUI chat_view 调用 chat(content) 获取逐 token 输出
- TUI 调用 switch_model() 实现 A5 会话内切换模型
"""

from typing import AsyncIterator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.core.config_manager import AppConfig
from src.core.session_manager import SessionManager


class ChatEngine:
    """对话引擎

    依赖注入 SessionManager 和 AppConfig，不直接持有 StorageBackend。
    """

    def __init__(self, session_mgr: SessionManager, config: AppConfig):
        self._session_mgr = session_mgr
        self._config = config

    # ==================================================================
    # A4/A5 — 构造 LLM 实例
    # ==================================================================

    def _build_llm(self) -> ChatOpenAI:
        """根据当前会话的 model_name 构造 ChatOpenAI 实例

        A5: 每次 chat() 调用时都重新构造，确保切换模型后立即生效。
        model_name 从 session_mgr.current_session 读取（已在 switch_model 中持久化）。
        """
        session = self._session_mgr.current_session
        assert session is not None
        return ChatOpenAI(
            model=session.model_name,
            api_key=self._config.env.api_key,
            base_url=self._config.env.api_base_url,
            timeout=self._config.llm.timeout,
            max_retries=self._config.llm.max_retries,
            stream_usage=True,
        )

    # ==================================================================
    # A1 — 历史消息 → LangChain 消息格式
    # ==================================================================

    @staticmethod
    def _to_langchain_messages(messages: list) -> list[BaseMessage]:
        """将 SessionManager 的消息列表转为 LangChain 消息格式"""
        result: list[BaseMessage] = []
        for msg in messages:
            content = msg.content
            if msg.role == "human":
                result.append(HumanMessage(content=content))
            elif msg.role == "ai":
                result.append(AIMessage(content=content))
            elif msg.role == "system":
                result.append(SystemMessage(content=content))
        return result

    # ==================================================================
    # A1/A2/A3 — 完整一轮对话
    # ==================================================================

    async def chat(self, content: str) -> AsyncIterator[str]:
        """执行一轮对话，逐 token 产出 LLM 回复

        一次调用完成：
        1. 保存用户消息
        2. 拉取全部历史
        3. 构造 LLM 并发起流式调用
        4. 逐 token yield
        5. 提取 token 统计并保存 AI 回复

        Args:
            content: 用户输入文本

        Yields:
            逐 token 的文本片段

        Raises:
            RuntimeError: 没有当前会话
        """
        # 1. 保存用户消息（同时触发 C7 标题自动生成）
        await self._session_mgr.add_user_message(content)

        # 2. 拉取全部历史并转为 LangChain 格式
        history = await self._session_mgr.get_messages()
        messages = self._to_langchain_messages(history)

        # 3. 构造 LLM
        llm = self._build_llm()

        # 4. 流式调用
        collected: list[str] = []
        usage_metadata = None
        async for chunk in llm.astream(messages):
            content_chunk = chunk.content if hasattr(chunk, "content") else ""
            if content_chunk:
                collected.append(content_chunk)
                yield content_chunk
            # 提取 usage_metadata（最后一条 chunk 携带）
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                usage_metadata = chunk.usage_metadata

        # 5. 提取 token 统计
        full_response = "".join(collected)
        prompt_tokens = 0
        completion_tokens = 0
        if usage_metadata:
            prompt_tokens = getattr(usage_metadata, "input_tokens", 0)
            completion_tokens = getattr(usage_metadata, "output_tokens", 0)

        # 6. 保存 AI 回复（E2 token 统计）
        await self._session_mgr.add_ai_message(
            content=full_response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    # ==================================================================
    # A5 — 切换模型
    # ==================================================================

    async def switch_model(self, model_name: str) -> None:
        """切换当前会话的模型并持久化

        A5: 只换 LLM 实例，历史上下文不动。
        model_name 持久化到数据库，重新 load_session 后可恢复。
        """
        await self._session_mgr.update_model(model_name)
