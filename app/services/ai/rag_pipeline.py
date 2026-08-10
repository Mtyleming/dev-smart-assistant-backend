"""RAG 检索链路：向量化 → 检索 → 重排 → 置信度 → 上下文组装。"""

from __future__ import annotations

import logging
from typing import Any, Literal

import tiktoken

from app.repositories.vector_repo import vector_repo
from app.services.ai.citation_verifier import verify_and_filter_citations
from app.services.ai.embedding_service import embedding_service
from app.services.ai.llm_client import RAG_SYSTEM_PROMPT, llm_client
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

    return "medium"


def format_numbered_context(chunks: list[dict[str, Any]]) -> str:
    """将 Top-N 切块格式化为 [1][2][3] 编号上下文。"""
    parts: list[str] = []
    for order, chunk in enumerate(chunks, start=1):
        content = str(chunk.get("content") or "").strip()
        document_id = chunk.get("document_id")
        parts.append(
            f"[{order}] {content}\n来源文档 ID: {document_id}"
        )
    return "\n\n".join(parts)


def assemble_context(
    chunks: list[dict[str, Any]],
    *,
    token_budget: int = _CONTEXT_TOKEN_BUDGET,
) -> tuple[str, list[dict[str, Any]]]:
    """按相关性从高到低拼接编号上下文；总 Token 超预算则从低相关截断。"""
    if not chunks:
        return "", []

    selected: list[dict[str, Any]] = []
    for chunk in chunks:
        candidate = [*selected, chunk]
        text = format_numbered_context(candidate)
        if _count_tokens(text) > token_budget:
            if not selected:
                encoding = tiktoken.get_encoding(_TOKEN_ENCODING)
                truncated_content = encoding.decode(
                    encoding.encode(str(chunk.get("content") or ""))[
                        : max(1, token_budget // 2)
                    ]
                )
                slim = {**chunk, "content": truncated_content}
                return format_numbered_context([slim]), [slim]
            break
        selected.append(chunk)

    return format_numbered_context(selected), selected


def take_recent_turns(
    messages: list[dict[str, Any]],
    *,
    max_turns: int = 3,
) -> list[dict[str, str]]:
    """取最近 N 轮 user/assistant 对话（不含当前尚未入库的提问时可含末条 user）。

    一轮 = 一条 user + 其后一条 assistant。若末尾只有 user，也计入一轮。
    """
    cleaned: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        cleaned.append({"role": role, "content": content})

    if not cleaned:
        return []

    # 从后向前按轮次切分
    turns: list[list[dict[str, str]]] = []
    i = len(cleaned) - 1
    while i >= 0 and len(turns) < max_turns:
        if cleaned[i]["role"] == "assistant":
            if i - 1 >= 0 and cleaned[i - 1]["role"] == "user":
                turns.append([cleaned[i - 1], cleaned[i]])
                i -= 2
            else:
                turns.append([cleaned[i]])
                i -= 1
        elif cleaned[i]["role"] == "user":
            turns.append([cleaned[i]])
            i -= 1
        else:
            i -= 1

    ordered: list[dict[str, str]] = []
    for turn in reversed(turns):
        ordered.extend(turn)
    return ordered


def build_rag_system_prompt(context_text: str) -> str:
    """系统提示词 + 编号知识库上下文段。"""
    context_block = context_text.strip() or "（本次未检索到可用片段）"
    return (
        f"{RAG_SYSTEM_PROMPT}\n\n"
        f"## 知识库上下文\n"
        f"{context_block}"
    )


class RAGPipeline:
    """向量检索 → 重排 → 置信度 → 上下文组装（生成由 chat 层负责流式输出）。"""

    async def retrieve(
        self,
        question: str,
        team_id: int,
        kb_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """仅执行检索与置信度判断，不调用大模型生成。

        Returns:
            {
              chunks, confidence, rerank_scores,
              context_text, use_retrieval
            }
        """
        kb_ids = list(kb_ids or [])
        question = (question or "").strip()
        empty = {
            "chunks": [],
            "confidence": "low",
            "rerank_scores": [],
            "context_text": "",
            "use_retrieval": False,
        }
        if not question:
            return empty

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
            return empty

        try:
            reranked = await rerank_chunks(
                question, candidates, top_n=_RERANK_TOP_N
            )
        except Exception as exc:
            logger.warning(
                "RAG 重排失败，按向量检索顺序降级（不影响回答）：%s",
                exc,
            )
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
            return {
                "chunks": top_chunks,
                "confidence": confidence,
                "rerank_scores": rerank_scores,
                "context_text": "",
                "use_retrieval": False,
            }

        context_text, used_chunks = assemble_context(top_chunks)
        return {
            "chunks": used_chunks,
            "confidence": confidence,
            "rerank_scores": rerank_scores,
            "context_text": context_text,
            "use_retrieval": True,
        }

    async def query(
        self,
        question: str,
        team_id: int,
        kb_ids: list[int] | None = None,
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """同步 RAG（供策略层）：检索 → 组装提示词 → 生成 → 引用校验。"""
        retrieved = await self.retrieve(question, team_id, kb_ids)
        confidence = retrieved["confidence"]
        chunks = retrieved["chunks"]
        rerank_scores = retrieved["rerank_scores"]

        if not retrieved["use_retrieval"]:
            answer = await llm_client.generate_general_fallback(question)
            return {
                "answer": answer,
                "sources": [],
                "confidence": confidence,
                "rerank_scores": rerank_scores,
            }

        system_prompt = build_rag_system_prompt(retrieved["context_text"])
        # history 不含当前问题；当前问题单独作为最后一条 user
        recent = take_recent_turns(history or [], max_turns=3)
        # 若最近一轮末尾已是当前问题（chat 已入库），去掉避免重复
        if recent and recent[-1]["role"] == "user" and recent[-1]["content"] == question:
            recent = recent[:-1]
            # 再保证最多 3 轮
            recent = take_recent_turns(recent, max_turns=3)

        messages = [*recent, {"role": "user", "content": question}]
        text = await llm_client.chat(messages, system_prompt=system_prompt)
        answer, sources, _cited = verify_and_filter_citations(text, chunks)
        if confidence == "medium" and _CONFIRM_HINT not in answer:
            answer = f"{answer}\n\n{_CONFIRM_HINT}"

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "rerank_scores": rerank_scores,
        }


rag_pipeline = RAGPipeline()
