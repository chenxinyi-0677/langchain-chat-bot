"""
能力扩展协议接口 —— H3/H4/H5

【What】
为后续功能预留的接口定义，仅包含方法签名，不实现任何逻辑。

【覆盖需求】
H3(图文上传)  H4(语音输入输出)  H5(工具调用)

【Why】
- 提前定义接口，确保后续实现时遵循统一的调用约定
- 与 UIProtocol 分离，避免基础接口膨胀

【Where】
- 各协议由对应的能力模块实现（如 AudioProtocol → src/audio/）
- TUI/WebUI 在运行时可检测某个协议是否被实现来决定是否展示对应菜单项
"""

from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class ImageProtocol(Protocol):
    """H3: 图文上传协议

    支持在对话中上传图片，LLM 根据图片内容生成回复。
    """

    async def chat_with_image(self, content: str, image_path: str) -> AsyncIterator[str]:
        """H3: 发送文本 + 图片，逐 token 接收回复

        Args:
            content: 用户输入的文本
            image_path: 图片文件的本地路径

        Yields:
            逐 token 的 LLM 回复文本片段
        """
        raise NotImplementedError("H3: 图文上传，后续实现")


@runtime_checkable
class AudioProtocol(Protocol):
    """H4: 语音输入输出协议

    支持将语音转文字后对话，以及将 LLM 回复合成为语音。
    """

    async def transcribe_audio(self, audio_path: str) -> str:
        """H4: 语音转文字（STT）

        Args:
            audio_path: 音频文件路径

        Returns:
            识别出的文本内容
        """
        raise NotImplementedError("H4: 语音输入，后续实现")

    async def synthesize_speech(self, text: str, output_path: str) -> str:
        """H4: 文字转语音（TTS）

        Args:
            text: 要合成的文本
            output_path: 输出音频文件路径

        Returns:
            生成的音频文件路径（同 output_path）
        """
        raise NotImplementedError("H4: 语音输出，后续实现")


@runtime_checkable
class ToolProtocol(Protocol):
    """H5: 工具调用协议

    支持在对话中注册和调用外部工具（如计算器、搜索、API 调用等）。
    """

    async def chat_with_tools(self, content: str, tools: list[dict]) -> AsyncIterator[str]:
        """H5: 发送文本 + 可用工具列表，逐 token 接收回复

        工具定义格式参考 OpenAI function calling:
        {"name": "search", "description": "...", "parameters": {...}}

        Args:
            content: 用户输入的文本
            tools: 可供 LLM 调用的工具定义列表

        Yields:
            逐 token 的 LLM 回复文本片段
        """
        raise NotImplementedError("H5: 工具调用，后续实现")
