"""Milvus 向量检索与清理封装。"""

import asyncio
import logging

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class VectorRepository:
    """向量库操作：检索相关文档切块、按知识库清理。"""

    async def search(
        self,
        question: str,
        team_id: str,
        kb_ids: list[str],
    ) -> list[dict]:
        """按问题与知识库范围检索切块（占位，后续 RAG 接入）。"""
        _ = (question, team_id, kb_ids)
        return []

    async def delete_by_knowledge_base(
        self, team_id: int, knowledge_base_id: int
    ) -> None:
        """
        删除某知识库在 Milvus 中的全部切块向量。

        过滤：knowledge_base_id == id AND team_id == team_id
        失败时抛出 AppException，调用方不得继续删 MySQL。
        """
        try:
            await asyncio.to_thread(
                self._delete_sync, int(team_id), int(knowledge_base_id)
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "Milvus 清理失败 team_id=%s kb_id=%s", team_id, knowledge_base_id
            )
            raise AppException(
                code=50301,
                message="向量数据清理失败，知识库未删除",
                status_code=503,
            ) from exc

    def _delete_sync(self, team_id: int, knowledge_base_id: int) -> None:
        """同步调用 pymilvus（在线程池中执行）。"""
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        collection = settings.milvus_collection
        expr = (
            f"knowledge_base_id == {knowledge_base_id} and team_id == {team_id}"
        )
        # 集合不存在时：视为无向量可清，直接成功（避免空环境删库被卡死）
        if not client.has_collection(collection_name=collection):
            logger.warning("Milvus collection 不存在，跳过清理: %s", collection)
            return
        client.delete(collection_name=collection, filter=expr)


vector_repo = VectorRepository()
