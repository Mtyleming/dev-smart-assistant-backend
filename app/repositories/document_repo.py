"""文档数据访问。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import Document, DocumentStatus, KnowledgeBase


class DocumentRepository:
    """documents 表 CRUD。"""

    async def create(
        self,
        db: AsyncSession,
        *,
        knowledge_base_id: int,
        title: str,
        file_type: str,
        file_path: str,
        file_size: int = 0,
        status: DocumentStatus = DocumentStatus.uploading,
    ) -> Document:
        """新增文档记录并 flush 拿到自增 ID。"""
        doc = Document(
            knowledge_base_id=knowledge_base_id,
            title=title,
            file_type=file_type,
            file_path=file_path,
            file_size=file_size,
            status=status,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        return doc

    async def get_by_id_and_team(
        self,
        db: AsyncSession,
        document_id: int,
        team_id: int,
        *,
        include_deleted: bool = False,
    ) -> Document | None:
        """按文档 ID + 团队查询；默认排除已软删。"""
        filters = [
            Document.id == document_id,
            KnowledgeBase.team_id == team_id,
        ]
        if not include_deleted:
            filters.append(Document.status != DocumentStatus.deleted)

        result = await db.execute(
            select(Document)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(*filters)
        )
        return result.scalar_one_or_none()

    async def page_by_kb(
        self,
        db: AsyncSession,
        *,
        knowledge_base_id: int,
        team_id: int,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[Document], int]:
        """分页列出知识库文档（排除已软删），按 updated_at 降序。"""
        filters = [
            Document.knowledge_base_id == knowledge_base_id,
            KnowledgeBase.team_id == team_id,
            Document.status != DocumentStatus.deleted,
        ]
        if keyword:
            filters.append(Document.title.like(f"%{keyword}%"))

        count_result = await db.execute(
            select(func.count())
            .select_from(Document)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(*filters)
        )
        total = int(count_result.scalar_one())

        result = await db.execute(
            select(Document)
            .join(KnowledgeBase, Document.knowledge_base_id == KnowledgeBase.id)
            .where(*filters)
            .order_by(Document.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update_file_meta(
        self,
        db: AsyncSession,
        doc: Document,
        *,
        file_path: str | None = None,
        file_size: int | None = None,
        full_text: str | None = None,
        set_full_text: bool = False,
        status: DocumentStatus | None = None,
    ) -> Document:
        """更新文件路径/大小/全文/状态。

        Args:
            db: 数据库会话。
            doc: 文档实体。
            file_path: 新路径；None 表示不改。
            file_size: 新大小；None 表示不改。
            full_text: 解析全文；需配合 set_full_text=True。
            set_full_text: 为 True 时写入 full_text（允许置空）。
            status: 新状态；None 表示不改。

        Returns:
            刷新后的文档实体。
        """
        if file_path is not None:
            doc.file_path = file_path
        if file_size is not None:
            doc.file_size = file_size
        if set_full_text:
            doc.full_text = full_text
        if status is not None:
            doc.status = status
        await db.flush()
        await db.refresh(doc)
        return doc

    async def soft_delete(self, db: AsyncSession, doc: Document) -> Document:
        """软删除：状态改为 deleted。"""
        doc.status = DocumentStatus.deleted
        await db.flush()
        await db.refresh(doc)
        return doc


document_repo = DocumentRepository()
