"""RAG 引用编号校验：校验回答中的 [1][2][3] 是否对应真实检索切块。"""

from __future__ import annotations

import re
from typing import Any

# 匹配回答中的引用编号，如 [1]、[2]
_CITATION_RE = re.compile(r"\[(\d+)\]")


def extract_citation_indices(text: str) -> list[int]:
    """按出现顺序提取引用编号（去重前保留顺序）。"""
    return [int(match.group(1)) for match in _CITATION_RE.finditer(text or "")]


def verify_and_filter_citations(
    answer: str,
    chunks: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[int]]:
    """校验回答中的引用编号，去掉无效编号，并返回真实引用的 sources。

    Args:
        answer: 模型完整回答。
        chunks: 本次注入提示词的 Top-N 切块（编号从 1 开始对应）。

    Returns:
        (清洗后的回答, 真实引用的 sources, 有效引用编号列表)
    """
    max_index = len(chunks)
    cited = extract_citation_indices(answer)
    valid_set = {idx for idx in cited if 1 <= idx <= max_index}
    invalid_set = {idx for idx in cited if idx not in valid_set}

    cleaned = answer
    for idx in sorted(invalid_set, reverse=True):
        cleaned = cleaned.replace(f"[{idx}]", "")
    # 压缩因删除编号产生的多余空白
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # 按首次出现顺序输出有效引用
    ordered_valid: list[int] = []
    for idx in cited:
        if idx in valid_set and idx not in ordered_valid:
            ordered_valid.append(idx)

    sources: list[dict[str, Any]] = []
    for idx in ordered_valid:
        chunk = chunks[idx - 1]
        sources.append(
            {
                "ref": idx,
                "document_id": chunk.get("document_id"),
                "chunk_index": chunk.get("chunk_index"),
                "knowledge_base_id": chunk.get("knowledge_base_id"),
                "score": chunk.get("score"),
                "chunk_id": chunk.get("chunk_id"),
                # 切片正文：前端展示 [n] 对应原文，避免只有编号无含义
                "content": str(chunk.get("content") or ""),
            }
        )
    return cleaned, sources, ordered_valid
