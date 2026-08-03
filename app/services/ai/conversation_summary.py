"""对话历史摘要 LangChain Tool。"""

import json
import logging
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.services.ai.llm_client import MAX_SUMMARY_LENGTH, llm_client

logger = logging.getLogger(__name__)


class SummarizeConversationInput(BaseModel):
    """对话摘要工具入参。"""

    messages_json: str = Field(
        description=(
            "JSON 格式的历史消息列表，每项包含 role（user/assistant/system）"
            "和 content 字段。示例：[{\"role\":\"user\",\"content\":\"你好\"}]"
        )
    )


async def summarize_messages(messages: list[dict[str, Any]]) -> str:
    """将历史消息压缩为 200 字以内摘要（供业务层直接调用）。"""
    valid_messages = [
        message
        for message in messages
        if str(message.get("content") or "").strip()
    ]
    summary = await llm_client.summarize_messages(valid_messages)
    return summary[:MAX_SUMMARY_LENGTH]


@tool(args_schema=SummarizeConversationInput)
async def summarize_conversation_history(messages_json: str) -> str:
    """将对话历史压缩为 200 字以内的中文摘要，用于系统提示词。

    当对话历史过长时，Agent 可调用此工具生成摘要，保留关键上下文与结论。
  """
    try:
        raw_messages = json.loads(messages_json)
    except json.JSONDecodeError as exc:
        logger.warning("摘要工具收到非法 JSON：%s", exc)
        return ""

    if not isinstance(raw_messages, list):
        logger.warning("摘要工具 messages_json 必须是数组")
        return ""

    messages = [item for item in raw_messages if isinstance(item, dict)]
    return await summarize_messages(messages)


# 供 Agent 创建时作为 tools 参数导入
summarize_conversation_history_tool = summarize_conversation_history

# Agent 默认工具集（后续创建 Agent 时直接展开传入）
DEFAULT_AGENT_TOOLS = [summarize_conversation_history_tool]
