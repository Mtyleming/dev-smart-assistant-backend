"""知识库查询路由策略（占位）。"""

from __future__ import annotations

import logging

from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)


class KnowledgeQueryRouteStrategy(IntentRouteStrategy):
    """对应意图 knowledge_query → LangGraph 节点 rag。"""

    intent = "knowledge_query"
    node_name = "rag"

    async def run(self, message: str, conversation_id: int) -> dict:
        """占位：后续接入 RAG 检索与生成。"""
        logger.info(
            "knowledge_query 占位执行 conversation_id=%s message_len=%s",
            conversation_id,
            len(message),
        )
        return {
            "intent": self.intent,
            "status": "placeholder",
            "answer": f"（占位）知识库查询尚未接入：{message[:100]}",
            "sources": [],
        }
