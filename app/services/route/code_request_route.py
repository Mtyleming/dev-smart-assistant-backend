"""代码辅助路由策略：解读 / 生成 / 改写分流。"""

from __future__ import annotations

import logging

from app.services.code_analysis_service import code_analysis_service
from app.services.code_generation_service import (
    code_generation_service,
    resolve_mode,
)
from app.services.code_parser import CodeParser
from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)


class CodeRequestRouteStrategy(IntentRouteStrategy):
    """对应意图 code_request → LangGraph 节点 code。"""

    intent = "code_request"
    node_name = "code"

    def __init__(self) -> None:
        self._parser = CodeParser()

    async def run(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
        content_type: str | None = None,
    ) -> dict:
        """按子模式执行解读、生成或改写。"""
        code, fence_lang = self._parser.extract_code(
            message, content_type=content_type
        )
        mode = resolve_mode(message, has_code=bool(code))

        logger.info(
            "code_request 分流 conversation_id=%s mode=%s code_len=%s "
            "team_id=%s content_type=%s",
            conversation_id,
            mode,
            len(code),
            team_id,
            content_type,
        )

        if mode in ("generate", "edit"):
            return await self._run_generate(
                message,
                conversation_id,
                team_id=team_id,
                kb_ids=kb_ids,
                content_type=content_type,
                hint_mode=mode,
            )

        return await self._run_analyze(
            message,
            conversation_id,
            code=code,
            fence_lang=fence_lang,
            team_id=team_id,
            kb_ids=kb_ids,
            content_type=content_type,
        )

    async def _run_generate(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None,
        kb_ids: list[int] | None,
        content_type: str | None,
        hint_mode: str,
    ) -> dict:
        """生成 / 改写路径。"""
        try:
            result = await code_generation_service.generate(
                message,
                conversation_id,
                team_id=team_id,
                kb_ids=kb_ids,
                content_type=content_type,
                hint_mode=hint_mode,  # type: ignore[arg-type]
            )
            return result
        except Exception as exc:
            logger.exception(
                "code_request 生成失败 conversation_id=%s: %s",
                conversation_id,
                exc,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": "代码生成暂时失败，请稍后重试。",
                "sources": [],
            }

    async def _run_analyze(
        self,
        message: str,
        conversation_id: int,
        *,
        code: str,
        fence_lang: str | None,
        team_id: int | None,
        kb_ids: list[int] | None,
        content_type: str | None,
    ) -> dict:
        """解读路径（沿用现有分析服务）。"""
        try:
            result = await code_analysis_service.analyze(
                message,
                content_type=content_type,
                code=code or None,
                fence_lang=fence_lang,
                team_id=team_id,
                kb_ids=kb_ids,
            )
            answer = code_analysis_service.format_answer(result)
            return {
                "intent": self.intent,
                "status": "ok",
                "answer": answer,
                "sources": result.get("sources") or [],
                "language": result.get("language"),
                "structure": result.get("structure"),
                "spec_injected": bool(result.get("spec_injected")),
                "mode": "analyze",
            }
        except ValueError as exc:
            logger.info(
                "code_request 业务校验失败 conversation_id=%s: %s",
                conversation_id,
                exc,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": str(exc),
                "sources": [],
            }
        except Exception as exc:
            logger.exception(
                "code_request 解读失败 conversation_id=%s: %s",
                conversation_id,
                exc,
            )
            return {
                "intent": self.intent,
                "status": "error",
                "answer": "代码解读暂时失败，请稍后重试。",
                "sources": [],
            }
