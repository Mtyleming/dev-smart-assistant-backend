"""文档切块（MySQL document_chunks）数据访问。"""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base_models import DocumentChunk


class DocumentChunkRepository:
    """document_chunks 表：批量写入与按文档/知识库清理。"""

    async def replace_for_document(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        knowledge_base_id: int,
        team_id: int,
        chunks: list[dict],
    ) -> list[DocumentChunk]:
        """覆盖写入某文档的全部切块（先删后插）。

        chunks 每项需含：chunk_id, chunk_index, content。
        """
        await self.delete_by_document(db, document_id=document_id, team_id=team_id)
        if not chunks:
            return []

        collection = settings.milvus_collection
        entities: list[DocumentChunk] = []
        for item in chunks:
            entity = DocumentChunk(
                chunk_id=str(item["chunk_id"]),
                document_id=document_id,
                chunk_index=int(item["chunk_index"]),
                content=str(item["content"] or ""),
                token_count=int(item.get("token_count") or 0),
                collection_name=collection,
                vector_id=item.get("vector_id"),
                knowledge_base_id=knowledge_base_id,
                team_id=team_id,
            )
            db.add(entity)
            entities.append(entity)
        await db.flush()
        return entities

    async def delete_by_document(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        team_id: int,
    ) -> int:
        """删除某文档在当前团队下的全部切块。"""
        result = await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.team_id == team_id,
            )
        )
        return int(result.rowcount or 0)

    async def delete_by_knowledge_base(
        self,
        db: AsyncSession,
        *,
        knowledge_base_id: int,
        team_id: int,
    ) -> int:
        """删除某知识库在当前团队下的全部切块。"""
        result = await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.knowledge_base_id == knowledge_base_id,
                DocumentChunk.team_id == team_id,
            )
        )
        return int(result.rowcount or 0)


document_chunk_repo = DocumentChunkRepository()
