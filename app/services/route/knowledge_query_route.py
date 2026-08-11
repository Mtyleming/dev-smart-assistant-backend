"""知识库查询路由策略：接入 RAG 检索与生成。"""

from __future__ import annotations

import logging

from app.services.ai.rag_pipeline import rag_pipeline
from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)


class KnowledgeQueryRouteStrategy(IntentRouteStrategy):
    """对应意图 knowledge_query → LangGraph 节点 rag。"""

    intent = "knowledge_query"
    node_name = "rag"

    async def run(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
        content_type: str | None = None,
    ) -> dict:
        """执行知识库 RAG 查询。"""
        _ = content_type
        if team_id is None:
            logger.warning(
                "knowledge_query 缺少 team_id conversation_id=%s",
                conversation_id,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": "缺少团队信息，无法查询知识库。",
                "sources": [],
                "confidence": "low",
                "rerank_scores": [],
            }

        logger.info(
            "knowledge_query 执行 conversation_id=%s team_id=%s kb_ids=%s message_len=%s",
            conversation_id,
            team_id,
            kb_ids,
            len(message),
        )
        try:
            result = await rag_pipeline.query(
                message,
                team_id=int(team_id),
                kb_ids=list(kb_ids or []),
            )
            return {
                "intent": self.intent,
                "status": "ok",
                "answer": result.get("answer") or "",
                "sources": result.get("sources") or [],
                "confidence": result.get("confidence") or "low",
                "rerank_scores": result.get("rerank_scores") or [],
            }
        except Exception as exc:
            logger.exception(
                "knowledge_query RAG 失败 conversation_id=%s team_id=%s: %s",
                conversation_id,
                team_id,
                exc,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": "知识库查询暂时失败，请稍后重试。",
                "sources": [],
                "confidence": "low",
                "rerank_scores": [],
            }
