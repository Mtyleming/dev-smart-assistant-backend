"""文档生成路由策略（占位）。"""

from __future__ import annotations

import logging

from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)


class DocGenerationRouteStrategy(IntentRouteStrategy):
    """对应意图 doc_generation → LangGraph 节点 doc。"""

    intent = "doc_generation"
    node_name = "doc"

    async def run(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
        content_type: str | None = None,
    ) -> dict:
        """占位：后续接入技术文档生成。"""
        _ = (team_id, kb_ids, content_type)
        logger.info(
            "doc_generation 占位执行 conversation_id=%s message_len=%s",
            conversation_id,
            len(message),
        )
        return {
            "intent": self.intent,
            "status": "placeholder",
            "answer": f"（占位）文档生成尚未接入：{message[:100]}",
            "sources": [],
        }
