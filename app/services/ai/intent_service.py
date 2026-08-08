"""意图识别服务：调用大模型将用户消息分类为四类意图之一。"""

from __future__ import annotations

import hashlib
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_qwq import ChatQwen

from app.core.config import settings

logger = logging.getLogger(__name__)

VALID_INTENTS = (
    "knowledge_query",
    "general_qa",
    "code_request",
    "doc_generation",
)

INTENT_SYSTEM_PROMPT = (
    "你是一个意图分类器。根据用户消息和对话历史，将意图分类为以下四类之一：\n"
    "1. knowledge_query：查询内部知识库中的技术文档、框架用法、编码规范等\n"
    "2. general_qa：通用技术问答，不依赖内部知识库\n"
    "3. code_request：请求解读、生成或审查代码\n"
    "4. doc_generation：请求生成技术文档\n\n"
    "注意：写代码、改代码、审查代码属于 code_request；"
    "生成 README/接口文档/设计文档属于 doc_generation。\n"
    '只输出一行 JSON，不要 Markdown，不要解释：{"intent":"类型","confidence":0.0}'
)

_JSON_BLOCK_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)

_intent_llm: ChatQwen | None = None
_intent_llm_config: tuple[str, str, str] | None = None


def _get_intent_llm() -> ChatQwen:
    """使用 settings 中已配置的 DashScope Key / Base / Model 创建 LLM。"""
    global _intent_llm, _intent_llm_config
    config = (settings.llm_api_key, settings.llm_api_base, settings.llm_model)
    if _intent_llm is None or _intent_llm_config != config:
        _intent_llm = ChatQwen(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_base,
            temperature=0,
            max_tokens=256,
            timeout=None,
            max_retries=2,
            # 意图分类不需要思考链，关闭后更稳定、更快返回 JSON
            enable_thinking=False,
        )
        _intent_llm_config = config
    return _intent_llm


def _default_result(confidence: float = 0.5) -> dict:
    """降级结果：回退到通用问答。"""
    return {"intent": "general_qa", "confidence": confidence}


def _extract_json_object(text: str) -> dict:
    """从模型输出中提取 JSON 对象（兼容多余文字 / Markdown 代码块）。"""
    content = (text or "").strip()
    if not content:
        raise json.JSONDecodeError("空响应", content, 0)

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    match = _JSON_BLOCK_RE.search(content)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed

    raise json.JSONDecodeError("未找到合法 JSON 对象", content, 0)


def _normalize_result(raw: dict) -> dict:
    """校验并规范化意图识别结果。"""
    intent = raw.get("intent")
    confidence = raw.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5

    if intent not in VALID_INTENTS:
        return _default_result(0.5)
    if confidence < 0.7:
        return {"intent": "general_qa", "confidence": confidence}
    return {"intent": intent, "confidence": confidence}


async def classify_intent(
    message: str,
    conversation_id: int,
    history: list[dict],
    redis_client,
) -> dict:
    """识别用户消息意图，结果缓存到 Redis（TTL 300 秒）。

    Returns:
        {"intent": str, "confidence": float}
    """
    msg_hash = hashlib.md5(message.encode()).hexdigest()[:16]
    cache_key = f"intent:{conversation_id}:{msg_hash}"

    cached = await redis_client.get(cache_key)
    if cached:
        try:
            return _normalize_result(json.loads(cached))
        except (json.JSONDecodeError, TypeError):
            logger.warning("意图缓存解析失败，将重新识别 cache_key=%s", cache_key)

    if not settings.llm_api_key:
        logger.warning("未配置 DASHSCOPE_API_KEY，意图识别降级为 general_qa")
        result = _default_result(0.5)
        await redis_client.set(cache_key, json.dumps(result), ex=300)
        return result

    history_text = "\n".join(
        f"{m.get('role', 'user')}: {str(m.get('content', ''))[:200]}"
        for m in history[-6:]
    )
    human_content = f"对话历史：\n{history_text}\n\n当前消息：{message}"

    try:
        response = await _get_intent_llm().ainvoke(
            [
                SystemMessage(content=INTENT_SYSTEM_PROMPT),
                HumanMessage(content=human_content),
            ]
        )
        content = response.content
        if not isinstance(content, str):
            content = str(content)
        result = _normalize_result(_extract_json_object(content))
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("意图识别结果解析失败，降级为 general_qa：%s", exc)
        result = _default_result(0.5)
    except Exception as exc:
        logger.warning("意图识别调用失败，降级为 general_qa：%s", exc)
        result = _default_result(0.5)

    await redis_client.set(cache_key, json.dumps(result), ex=300)
    return result
