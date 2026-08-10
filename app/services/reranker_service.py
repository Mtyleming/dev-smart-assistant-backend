"""百炼文本重排服务（默认 gte-rerank-v2）。

说明：官方示例有时写作 TextReRanking；当前 dashscope SDK 导出名为 TextReRank。
旧模型名 gte-rerank 若未开通会返回 403 Access denied，请改用 gte-rerank-v2
或在百炼控制台模型广场开通对应模型。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class RerankAccessDeniedError(RuntimeError):
    """重排模型未开通或 API Key 无权限。"""


def _rerank_sync(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_n: int,
) -> list[dict[str, Any]]:
    """同步调用 DashScope TextReRank。"""
    from dashscope import TextReRank

    if not candidates:
        return []

    api_key = settings.llm_api_key
    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法进行文本重排")

    model = settings.rerank_model
    texts = [str((c.get("entity") or {}).get("content") or "") for c in candidates]
    response = TextReRank.call(
        model=model,
        query=query,
        documents=texts,
        top_n=min(top_n, len(candidates)),
        api_key=api_key,
    )

    output = getattr(response, "output", None)
    results = getattr(output, "results", None) if output is not None else None
    if results is None and isinstance(response, dict):
        results = (response.get("output") or {}).get("results")
    if not results:
        status = getattr(response, "status_code", None)
        message = str(
            getattr(response, "message", None) or getattr(response, "code", None) or ""
        )
        code = str(getattr(response, "code", None) or "")
        if status == 403 or "Access denied" in message or "AccessDenied" in code:
            raise RerankAccessDeniedError(
                f"文本重排模型无权访问（model={model}, status={status}）。"
                "请到阿里云百炼控制台 → 模型广场开通「文本排序 / gte-rerank-v2」，"
                "或在 .env 设置 RERANK_MODEL=gte-rerank-v2 后重试。"
                f" 原始信息: {message}"
            )
        raise RuntimeError(
            f"文本重排失败 model={model} status={status} message={message}"
        )

    reranked: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict):
            index = int(item["index"])
            score = float(item.get("relevance_score") or item.get("score") or 0.0)
        else:
            index = int(item.index)
            score = float(getattr(item, "relevance_score", 0.0) or 0.0)
        if index < 0 or index >= len(candidates):
            continue
        original = candidates[index]
        entity = original.get("entity") or {}
        reranked.append(
            {
                "content": entity.get("content") or "",
                "document_id": entity.get("document_id"),
                "chunk_index": entity.get("chunk_index"),
                "knowledge_base_id": entity.get("knowledge_base_id"),
                "chunk_id": entity.get("chunk_id"),
                "score": score,
            }
        )
    reranked.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
    return reranked


async def rerank_chunks(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """对向量检索候选切块做文本相关性重排。

    candidates 需为 Milvus hit 格式：{"entity": {...}, "distance": ...}
    返回按 relevance_score 降序的切块列表。
    """
    if not candidates:
        return []
    try:
        return await asyncio.to_thread(
            _rerank_sync, query, candidates, top_n=top_n
        )
    except RerankAccessDeniedError as exc:
        # 权限类错误：上层会降级，不必打完整堆栈吓到开发者
        logger.warning("%s", exc)
        raise
    except Exception:
        logger.exception(
            "文本重排失败 model=%s query_len=%s candidates=%s",
            settings.rerank_model,
            len(query),
            len(candidates),
        )
        raise
