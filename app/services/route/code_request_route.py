"""代码辅助路由策略（占位）。"""

from __future__ import annotations

import logging

from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)


class CodeRequestRouteStrategy(IntentRouteStrategy):
    """对应意图 code_request → LangGraph 节点 code。"""

    intent = "code_request"
    node_name = "code"

    async def run(self, message: str, conversation_id: int) -> dict:
        """占位：后续接入代码解读 / 生成 / 审查。"""
        logger.info(
            "code_request 占位执行 conversation_id=%s message_len=%s",
            conversation_id,
            len(message),
        )
        return {
            "intent": self.intent,
            "status": "placeholder",
            "answer": f"（占位）代码辅助尚未接入：{message[:100]}",
            "sources": [],
        }
