"""百炼文本向量化工具：上传索引与 RAG 查询共用。"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """封装 text-embedding-v4（默认 1024 维）批量向量化。"""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量化（百炼 OpenAI 兼容接口）。

        单次请求最多 embedding_batch_size 条（默认 10），自动分批合并。
        未配置 API Key 或调用失败时抛出异常。
        """
        if not texts:
            return []

        api_key = self._settings.llm_api_key
        if not api_key:
            raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法进行文本向量化")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=self._settings.llm_api_base,
        )
        model = self._settings.embedding_model
        dimensions = self._settings.embedding_dimensions
        batch_size = max(1, int(self._settings.embedding_batch_size))

        vectors: list[list[float]] = []
        try:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                response = await client.embeddings.create(
                    model=model,
                    input=batch,
                    dimensions=dimensions,
                    encoding_format="float",
                )
                # API 按 index 回传，排序后保证与输入顺序一致
                ordered = sorted(response.data, key=lambda item: item.index)
                vectors.extend([list(item.embedding) for item in ordered])
        except Exception as exc:
            logger.warning("文本向量化失败：%s", exc)
            raise
        finally:
            await client.close()

        if len(vectors) != len(texts):
            raise RuntimeError(
                f"向量数量与文本数量不一致：texts={len(texts)} vectors={len(vectors)}"
            )
        return vectors


embedding_service = EmbeddingService()
