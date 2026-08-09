"""百炼文本重排（gte-rerank）服务。

说明：官方示例有时写作 TextReRanking；当前 dashscope SDK 导出名为 TextReRank。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def _rerank_sync(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_n: int,
) -> list[dict[str, Any]]:
    """同步调用 DashScope TextReRanking。"""
    from dashscope import TextReRank

    if not candidates:
        return []

    api_key = settings.llm_api_key
    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法进行文本重排")

    texts = [str((c.get("entity") or {}).get("content") or "") for c in candidates]
    response = TextReRank.call(
        model=settings.rerank_model,
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
        message = getattr(response, "message", None) or getattr(response, "code", None)
        raise RuntimeError(f"文本重排失败 status={status} message={message}")

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
    except Exception:
        logger.exception("文本重排失败 query_len=%s candidates=%s", len(query), len(candidates))
        raise
