"""RAG 检索链路：向量化 → 检索 → 重排 → 置信度 → 上下文组装 → 生成。"""

from __future__ import annotations

import logging
from typing import Any, Literal

import tiktoken

from app.repositories.vector_repo import vector_repo
from app.services.ai.embedding_service import embedding_service
from app.services.ai.llm_client import llm_client
from app.services.reranker_service import rerank_chunks

logger = logging.getLogger(__name__)

ConfidenceLevel = Literal["high", "medium", "low"]

_RETRIEVE_TOP_K = 5
_RERANK_TOP_N = 5
_CONTEXT_TOP_N = 3
_CONTEXT_TOKEN_BUDGET = 4000
_HIGH_SCORE = 0.8
_MEDIUM_SCORE = 0.5
_CONSISTENCY_SCORE = 0.5
_CONFIRM_HINT = "建议进一步确认"
_TOKEN_ENCODING = "cl100k_base"


def _count_tokens(text: str) -> int:
    """按 cl100k_base 统计 Token 数。"""
    try:
        encoding = tiktoken.get_encoding(_TOKEN_ENCODING)
        return len(encoding.encode(text or ""))
    except Exception:
        # 降级：粗略按字符估算
        return max(1, len(text or "") // 2)


def _judge_confidence(chunks: list[dict[str, Any]]) -> ConfidenceLevel:
    """根据 Top-1 Reranker 分数与多块一致性判断置信度。"""
    if not chunks:
        return "low"

    top1 = float(chunks[0].get("score") or 0.0)
    if top1 < _MEDIUM_SCORE:
        return "low"

    others = chunks[1:_CONTEXT_TOP_N]
    consistent = all(
        float(item.get("score") or 0.0) >= _CONSISTENCY_SCORE for item in others
    )

    if top1 >= _HIGH_SCORE and consistent:
        return "high"

    # Top-1 高分但不一致，或中等分数 → 中置信度
    return "medium"


def _format_chunk_block(chunk: dict[str, Any], order: int) -> str:
    """将单一切块格式化为带来源元数据的上下文块。"""
    document_id = chunk.get("document_id")
    chunk_index = chunk.get("chunk_index")
    content = str(chunk.get("content") or "").strip()
    return (
        f"[片段{order}|document_id={document_id}|chunk_index={chunk_index}]\n"
        f"{content}"
    )


def assemble_context(
    chunks: list[dict[str, Any]],
    *,
    token_budget: int = _CONTEXT_TOKEN_BUDGET,
) -> tuple[str, list[dict[str, Any]]]:
    """按相关性从高到低拼接上下文；总 Token 超预算则从低相关截断。

    返回 (context_text, used_chunks)。
    """
    if not chunks:
        return "", []

    # 先按相关性从高到低尝试纳入，超预算则停止（等价于丢弃更低相关块）
    selected: list[dict[str, Any]] = []
    parts: list[str] = []
    used_tokens = 0
    for order, chunk in enumerate(chunks, start=1):
        block = _format_chunk_block(chunk, order)
        block_tokens = _count_tokens(block)
        # 块之间换行分隔也计入粗略预算
        sep_tokens = 1 if parts else 0
        if used_tokens + sep_tokens + block_tokens > token_budget:
            if not selected:
                # 单块过大：截断内容以塞入预算
                encoding = tiktoken.get_encoding(_TOKEN_ENCODING)
                truncated = encoding.decode(
                    encoding.encode(block)[: max(1, token_budget)]
                )
                return truncated, [chunk]
            break
        parts.append(block)
        selected.append(chunk)
        used_tokens += sep_tokens + block_tokens

    return "\n\n".join(parts), selected


class RAGPipeline:
    """向量检索 → 重排 → 置信度 → 上下文组装 → 回答生成。"""

    async def query(
        self,
        question: str,
        team_id: int,
        kb_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """执行 RAG 并返回回答与来源引用。"""
        kb_ids = list(kb_ids or [])
        question = (question or "").strip()
        if not question:
            return {
                "answer": "请提供有效的问题。",
                "sources": [],
                "confidence": "low",
                "rerank_scores": [],
            }

        vectors = await embedding_service.embed([question])
        query_vector = vectors[0]
        candidates = await vector_repo.search(
            query_vector,
            team_id=team_id,
            kb_ids=kb_ids,
            top_k=_RETRIEVE_TOP_K,
        )
        logger.info(
            "RAG 向量检索完成 team_id=%s kb_ids=%s hits=%s",
            team_id,
            kb_ids,
            len(candidates),
        )

        if not candidates:
            answer = await llm_client.generate_general_fallback(question)
            return {
                "answer": answer,
                "sources": [],
                "confidence": "low",
                "rerank_scores": [],
            }

        try:
            reranked = await rerank_chunks(
                question, candidates, top_n=_RERANK_TOP_N
            )
        except Exception as exc:
            logger.warning("RAG 重排失败，按向量检索顺序降级：%s", exc)
            # 无 Reranker 分数时给中等分，仍走检索回答并提示确认
            reranked = [
                {
                    "content": (hit.get("entity") or {}).get("content") or "",
                    "document_id": (hit.get("entity") or {}).get("document_id"),
                    "chunk_index": (hit.get("entity") or {}).get("chunk_index"),
                    "knowledge_base_id": (hit.get("entity") or {}).get(
                        "knowledge_base_id"
                    ),
                    "chunk_id": (hit.get("entity") or {}).get("chunk_id"),
                    "score": 0.6,
                }
                for hit in candidates
            ]

        top_chunks = reranked[:_CONTEXT_TOP_N]
        confidence = _judge_confidence(top_chunks)
        rerank_scores = [float(c.get("score") or 0.0) for c in top_chunks]

        if confidence == "low":
            answer = await llm_client.generate_general_fallback(question)
            return {
                "answer": answer,
                "sources": [],
                "confidence": confidence,
                "rerank_scores": rerank_scores,
            }

        context, used_chunks = assemble_context(top_chunks)
        generated = await llm_client.generate(question, used_chunks, context=context)
        answer = str(generated.get("text") or "").strip()
        if confidence == "medium" and _CONFIRM_HINT not in answer:
            answer = f"{answer}\n\n{_CONFIRM_HINT}"

        return {
            "answer": answer,
            "sources": generated.get("sources") or [],
            "confidence": confidence,
            "rerank_scores": rerank_scores,
        }


rag_pipeline = RAGPipeline()
