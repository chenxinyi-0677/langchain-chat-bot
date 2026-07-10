"""
多模型并行对比 —— Comparator

【What】
将同一个 prompt 同时发送给多个模型，并发收集结果后一次性返回，
方便对比不同模型的输出质量和 token 消耗。

【覆盖需求】
H2(多模型并行对比)

【Why】
- 不依赖 SessionManager / ChatEngine——不需要 session 概念，不持久化
- 独立模块，只取 AppConfig 中的 LLM 参数（api_base / api_key / timeout / max_retries）

【Where】
- TUI compare 命令调用 Comparator.compare(prompt, model_names)
- 结果一次性返回后由 UI 层展示对比表格
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from src.core.config_manager import AppConfig

_LOGGER = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """单个模型的调用结果"""

    model_name: str
    response: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None


class Comparator:
    """多模型对比器

    创建时注入 AppConfig，compare() 每次调用时根据传入的模型名列表
    并发构造 LLM 实例并发起流式调用。
    """

    def __init__(self, config: AppConfig):
        self._config = config

    def _build_llm(self, model_name: str) -> ChatOpenAI:
        return ChatOpenAI(
            model=model_name,
            api_key=self._config.env.api_key,
            base_url=self._config.env.api_base_url,
            timeout=self._config.llm.timeout,
            max_retries=self._config.llm.max_retries,
            stream_usage=True,
        )

    async def _call_single(self, model_name: str, prompt: str) -> ModelResult:
        """调用单个模型，内部 try/except 确保异常不会外抛"""
        try:
            llm = self._build_llm(model_name)
            messages = [HumanMessage(content=prompt)]
            collected: list[str] = []
            usage_metadata = None
            async for chunk in llm.astream(messages):
                content_chunk = chunk.content if hasattr(chunk, "content") else ""
                if content_chunk:
                    collected.append(content_chunk)
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    usage_metadata = chunk.usage_metadata
            prompt_tokens = 0
            completion_tokens = 0
            if usage_metadata:
                prompt_tokens = getattr(usage_metadata, "input_tokens", 0)
                completion_tokens = getattr(usage_metadata, "output_tokens", 0)
            return ModelResult(
                model_name=model_name,
                response="".join(collected),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception as e:
            _LOGGER.warning("Model comparison failed", extra={"model_name": model_name, "error": str(e)})
            return ModelResult(model_name=model_name, error=str(e))

    async def compare(self, prompt: str, model_names: list[str]) -> list[ModelResult]:
        """将 prompt 并发发送给多个模型，返回结果列表

        每个模型的调用在独立协程中执行，内部 try/except 捕获异常，
        单个模型失败不影响其他模型的结果收集。

        Args:
            prompt: 用户输入的提示词
            model_names: 要调用的模型名称列表

        Returns:
            ModelResult 列表，顺序与 model_names 一致
        """
        tasks = [self._call_single(name, prompt) for name in model_names]
        return await asyncio.gather(*tasks)
