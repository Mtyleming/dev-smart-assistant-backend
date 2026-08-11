"""代码辅助路由策略：解读已接入，生成暂占位。"""

from __future__ import annotations

import logging
import re

from app.services.code_analysis_service import code_analysis_service
from app.services.code_parser import CodeParser
from app.services.route.base import IntentRouteStrategy

logger = logging.getLogger(__name__)

# 明显「生成代码」类请求
_GENERATE_KEYWORDS = (
    "帮我写",
    "帮我生成",
    "请生成",
    "生成一段",
    "生成一个",
    "生成代码",
    "写一段",
    "写一个",
    "写个",
    "实现一个",
    "实现一段",
    "给我写",
    "创建一段",
    "创建一个",
)

_GENERATE_RE = re.compile(
    "|".join(re.escape(k) for k in _GENERATE_KEYWORDS),
)


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
        """代码解读；生成类请求本期返回开发中提示。"""
        code, fence_lang = self._parser.extract_code(
            message, content_type=content_type
        )
        wants_generate = bool(_GENERATE_RE.search(message or ""))

        # 有生成意图且抽不出代码 → 生成功能占位
        if wants_generate and not code:
            logger.info(
                "code_request 生成占位 conversation_id=%s",
                conversation_id,
            )
            return {
                "intent": self.intent,
                "status": "pending_generate",
                "answer": "代码生成功能开发中，当前仅支持粘贴代码进行解读分析。",
                "sources": [],
            }

        logger.info(
            "code_request 解读执行 conversation_id=%s team_id=%s kb_ids=%s "
            "content_type=%s code_len=%s",
            conversation_id,
            team_id,
            kb_ids,
            content_type,
            len(code),
        )
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
