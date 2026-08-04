"""百炼平台大模型调用封装。"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_qwq import ChatQwen
from openai import AuthenticationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_SUMMARY_LENGTH = 200

ROLE_LABELS = {
    "user": "用户",
    "assistant": "助手",
    "system": "系统",
}

SUMMARY_SYSTEM_PROMPT = (
    "你是专业的对话摘要助手。请将用户提供的对话历史压缩为简洁的中文摘要，"
    "保留关键上下文、重要结论和未解决问题。"
    "摘要必须不超过200字，只输出摘要正文，不要添加标题或额外说明。"
)

_llm: ChatQwen | None = None
_llm_config_key: tuple[str, str, str] | None = None


def _get_llm(api_key: str, api_base: str, model: str) -> ChatQwen:
    """按需创建 ChatQwen 实例，避免未配置 Key 时模块导入失败。"""
    global _llm, _llm_config_key
    config_key = (api_key, api_base, model)
    if _llm is None or _llm_config_key != config_key:
        _llm = ChatQwen(
            model=model,
            api_key=api_key,
            base_url=api_base,
            max_tokens=3_000,
            timeout=None,
            max_retries=2,
        )
        _llm_config_key = config_key
    return _llm


def _format_messages_for_summary(messages: list[dict[str, Any]]) -> str:
    """将消息列表格式化为可读对话文本。"""
    lines: list[str] = []
    for message in messages:
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        role = str(message.get("role") or "user")
        label = ROLE_LABELS.get(role, role)
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _truncate_summary(text: str) -> str:
    """将摘要截断到最大长度。"""
    return text.strip()[:MAX_SUMMARY_LENGTH]


def _fallback_summary(formatted: str) -> str:
    """API 不可用或调用失败时的降级摘要。"""
    compact = " ".join(formatted.split())
    return _truncate_summary(compact)


class LLMClient:
    """封装 DashScope / 百炼 API，屏蔽 SDK 细节。"""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def generate(self, question: str, chunks: list[dict]) -> dict:
        """
        根据问题与检索切块生成回答。

        返回纯数据：{"text": str, "sources": list}
        """
        _ = (question, chunks, self._settings.llm_api_key)
        return {
            "text": "（骨架占位）大模型尚未接入，请稍后配置 DASHSCOPE_API_KEY。",
            "sources": [],
        }

    async def summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        """将历史消息压缩为不超过 200 字的中文摘要。"""
        if not messages:
            return ""

        formatted = _format_messages_for_summary(messages)
        if not formatted:
            return ""

        if not self._settings.llm_api_key:
            logger.warning("未配置 DASHSCOPE_API_KEY，使用降级摘要")
            return _fallback_summary(formatted)

        try:
            response = await _get_llm(
                self._settings.llm_api_key,
                self._settings.llm_api_base,
                self._settings.llm_model,
            ).ainvoke(
                [
                    SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
                    HumanMessage(content=f"以下是对话历史：\n\n{formatted}"),
                ]
            )
            content = response.content
            if not isinstance(content, str):
                content = str(content)
            return _truncate_summary(content)
        except Exception as exc:
            logger.warning("摘要生成失败，使用降级摘要：%s", exc)
            return _fallback_summary(formatted)

    def _build_lc_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        system_prompt: str | None = None,
    ) -> list[SystemMessage | HumanMessage | AIMessage]:
        """将业务消息列表转换为 LangChain 消息格式。"""
        lc_messages: list[SystemMessage | HumanMessage | AIMessage] = []
        if system_prompt:
            lc_messages.append(SystemMessage(content=system_prompt))

        for message in messages:
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant":
                lc_messages.append(AIMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        return lc_messages

    def _placeholder_reply(self, messages: list[dict[str, Any]]) -> str:
        """未配置 API Key 时的占位回复。"""
        last_user = next(
            (
                str(message.get("content") or "")
                for message in reversed(messages)
                if message.get("role") == "user"
            ),
            "",
        )
        return f"（骨架占位）已收到你的消息：{last_user[:100]}"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        system_prompt: str | None = None,
    ) -> str:
        """根据对话上下文生成助手回复。"""
        if not messages:
            return ""

        lc_messages = self._build_lc_messages(messages, system_prompt=system_prompt)

        if not self._settings.llm_api_key:
            logger.warning("未配置 DASHSCOPE_API_KEY，返回占位回复")
            return self._placeholder_reply(messages)

        try:
            response = await _get_llm(
                self._settings.llm_api_key,
                self._settings.llm_api_base,
                self._settings.llm_model,
            ).ainvoke(lc_messages)
            content = response.content
            if not isinstance(content, str):
                content = str(content)
            return content.strip()
        except AuthenticationError as exc:
            logger.error(
                "DashScope 认证失败，请检查 DASHSCOPE_API_KEY 是否有效，"
                "以及 DASHSCOPE_API_BASE 是否与 Key 所属站点一致（国内/国际）"
            )
            raise ValueError(
                "大模型 API Key 认证失败，请检查 .env 中的 DASHSCOPE_API_KEY 与 DASHSCOPE_API_BASE"
            ) from exc
        except Exception as exc:
            logger.warning("对话生成失败：%s", exc)
            raise

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """流式生成助手回复，逐块 yield 文本内容。"""
        if not messages:
            return

        lc_messages = self._build_lc_messages(messages, system_prompt=system_prompt)

        if not self._settings.llm_api_key:
            logger.warning("未配置 DASHSCOPE_API_KEY，返回占位回复")
            yield self._placeholder_reply(messages)
            return

        try:
            async for chunk in _get_llm(
                self._settings.llm_api_key,
                self._settings.llm_api_base,
                self._settings.llm_model,
            ).astream(lc_messages):
                content = chunk.content
                if not content:
                    continue
                if not isinstance(content, str):
                    content = str(content)
                yield content

        except Exception as exc:
            logger.warning("对话流式生成失败：%s", exc)
            raise

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """文本向量化（骨架占位）。"""
        _ = texts
        return []


llm_client = LLMClient()
