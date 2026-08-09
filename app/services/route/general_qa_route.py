"""通用问答路由策略（占位）。"""

from __future__ import annotations

import logging

from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)


class GeneralQaRouteStrategy(IntentRouteStrategy):
    """对应意图 general_qa → LangGraph 节点 general。"""

    intent = "general_qa"
    node_name = "general"

    async def run(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
    ) -> dict:
        """占位：后续接入通用大模型问答。"""
        _ = (team_id, kb_ids)
        logger.info(
            "general_qa 占位执行 conversation_id=%s message_len=%s",
            conversation_id,
            len(message),
        )
        return {
            "intent": self.intent,
            "status": "placeholder",
            "answer": f"（占位）通用问答尚未接入：{message[:100]}",
            "sources": [],
        }
