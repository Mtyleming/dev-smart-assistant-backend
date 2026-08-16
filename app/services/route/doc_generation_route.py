"""文档生成路由策略：接入 templateDoc 生成链路。"""

from __future__ import annotations

import logging

from app.core.database import async_session_factory
from app.services.route.base import IntentRouteStrategy
from app.templateDoc.template import (
    document_generation_service,
    infer_doc_type,
)

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
        """根据用户消息生成 Markdown 技术文档。"""
        if team_id is None:
            logger.warning(
                "doc_generation 缺少 team_id conversation_id=%s",
                conversation_id,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": "缺少团队信息，无法生成文档。",
                "sources": [],
            }

        doc_type = infer_doc_type(message)
        is_code = str(content_type or "").lower() == "code" or "```" in (message or "")
        logger.info(
            "doc_generation 执行 conversation_id=%s team_id=%s doc_type=%s is_code=%s",
            conversation_id,
            team_id,
            doc_type.value,
            is_code,
        )
        try:
            async with async_session_factory() as db:
                result = await document_generation_service.generate(
                    db,
                    doc_type,
                    message,
                    int(team_id),
                    is_code=is_code,
                    kb_ids=list(kb_ids or []),
                )
            return {
                "intent": self.intent,
                "status": "ok",
                "answer": result.get("content") or "",
                "sources": [],
                "doc_type": result.get("doc_type"),
                "template_source": result.get("template_source"),
                "style_used": bool(result.get("style_used")),
            }
        except Exception as exc:
            logger.exception(
                "doc_generation 失败 conversation_id=%s team_id=%s: %s",
                conversation_id,
                team_id,
                exc,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": "文档生成暂时失败，请稍后重试。",
                "sources": [],
            }
