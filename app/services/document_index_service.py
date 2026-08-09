"""文档索引编排：切块 → MySQL 落库 → 向量化 → 写入 Milvus（无 HTTP 接口）。"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.repositories.document_chunk_repo import document_chunk_repo
from app.repositories.vector_repo import vector_repo
from app.services.ai.embedding_service import embedding_service
from app.services.document_chunker import split_text

logger = logging.getLogger(__name__)


class DocumentIndexService:
    """将已解析全文切块入库并写入向量库；切片与 Embedding 各自解耦。"""

    async def index_document(
        self,
        db: AsyncSession,
        *,
        document_id: int,
        knowledge_base_id: int,
        team_id: int,
        full_text: str | None,
    ) -> None:
        """切块写入 MySQL document_chunks，再向量化写入 Milvus。

        无可索引文本时清空旧切块并返回。
        切片 / Embedding / 写入失败时抛出 AppException，由调用方将文档标为 failed。
        """
        chunks = split_text(full_text)
        if not chunks:
            await document_chunk_repo.delete_by_document(
                db, document_id=document_id, team_id=team_id
            )
            await db.commit()
            logger.info(
                "文档无可索引文本，跳过向量化 document_id=%s", document_id
            )
            return

        chunk_rows = [
            {
                "chunk_id": f"{document_id}_{chunk.chunk_index}",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
            }
            for chunk in chunks
        ]
        # 先落 MySQL 切片表，再去做 Embedding / Milvus
        await document_chunk_repo.replace_for_document(
            db,
            document_id=document_id,
            knowledge_base_id=knowledge_base_id,
            team_id=team_id,
            chunks=chunk_rows,
        )
        await db.commit()

        texts = [chunk.content for chunk in chunks]
        try:
            vectors = await embedding_service.embed(texts)
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "文档向量化失败 document_id=%s", document_id
            )
            raise AppException(
                code=50303,
                message="文档向量化失败",
                status_code=503,
            ) from exc

        milvus_rows = [
            {
                "chunk_id": f"{document_id}_{chunk.chunk_index}",
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "vector": vectors[i],
                "knowledge_base_id": knowledge_base_id,
                "team_id": team_id,
            }
            for i, chunk in enumerate(chunks)
        ]
        await vector_repo.upsert_chunks(milvus_rows)
        logger.info(
            "文档索引完成 document_id=%s chunks=%s", document_id, len(milvus_rows)
        )


document_index_service = DocumentIndexService()
