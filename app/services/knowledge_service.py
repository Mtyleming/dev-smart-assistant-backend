"""知识库业务逻辑（含文档上传/查询/删除）。"""

from typing import Any

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppException, ConflictError, NotFoundError
from app.core.file_storage import (
    build_relative_path,
    resolve_file_type,
    save_upload_file,
    title_from_filename,
)
from app.models.base_models import Document, DocumentStatus, KnowledgeBase
from app.repositories.document_repo import document_repo
from app.repositories.knowledge_repo import knowledge_repo
from app.repositories.vector_repo import vector_repo
from app.schemas.knowledge import (
    DocumentCreateData,
    DocumentIdRequest,
    DocumentItem,
    DocumentPageData,
    DocumentPageRequest,
    KnowledgeCreateData,
    KnowledgeCreateRequest,
    KnowledgeIdRequest,
    KnowledgeItem,
    KnowledgePageData,
    KnowledgePageRequest,
    KnowledgeUpdateRequest,
)
from app.services.document_parser import DocumentParseError, parse_document


def _to_item(kb: KnowledgeBase) -> KnowledgeItem:
    return KnowledgeItem(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        team_id=kb.team_id,
        created_by=kb.created_by,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


def _to_document_item(doc: Document, *, include_full_text: bool = False) -> DocumentItem:
    return DocumentItem(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        title=doc.title,
        file_type=doc.file_type,
        file_path=doc.file_path,
        file_size=doc.file_size,
        status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        full_text=doc.full_text if include_full_text else None,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


class KnowledgeService:
    """知识库管理业务。"""

    @staticmethod
    def _team_id(user: dict[str, Any]) -> int:
        return int(user["team_id"])

    @staticmethod
    def _user_id(user: dict[str, Any]) -> int:
        return int(user["id"])

    async def create(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeCreateRequest,
    ) -> KnowledgeCreateData:
        team_id = self._team_id(user)
        name = body.name.strip()
        exists = await knowledge_repo.get_by_team_and_name(db, team_id, name)
        if exists:
            raise ConflictError("知识库名称已存在")

        kb = await knowledge_repo.create(
            db,
            name=name,
            description=body.description,
            team_id=team_id,
            created_by=self._user_id(user),
        )
        await db.commit()
        return KnowledgeCreateData(id=kb.id)

    async def page(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgePageRequest,
    ) -> KnowledgePageData:
        team_id = self._team_id(user)
        keyword = body.keyword.strip() if body.keyword else None
        items, total = await knowledge_repo.page_by_team(
            db,
            team_id,
            page=body.page,
            page_size=body.page_size,
            keyword=keyword or None,
        )
        return KnowledgePageData(
            items=[_to_item(kb) for kb in items],
            total=total,
            page=body.page,
        )

    async def get_by_id(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeIdRequest,
    ) -> KnowledgeItem:
        kb = await knowledge_repo.get_by_id_and_team(
            db, body.id, self._team_id(user)
        )
        if not kb:
            raise NotFoundError("知识库不存在")
        return _to_item(kb)

    async def update(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeUpdateRequest,
    ) -> None:
        team_id = self._team_id(user)
        kb = await knowledge_repo.get_by_id_and_team(db, body.id, team_id)
        if not kb:
            raise NotFoundError("知识库不存在")

        fields = body.model_fields_set
        new_name = None
        if "name" in fields:
            new_name = body.name.strip() if body.name else body.name
            dup = await knowledge_repo.get_by_team_and_name(
                db, team_id, new_name, exclude_id=kb.id
            )
            if dup:
                raise ConflictError("知识库名称已存在")

        set_description = "description" in fields
        await knowledge_repo.update(
            db,
            kb,
            name=new_name,
            description=body.description if set_description else None,
            set_description=set_description,
        )
        await db.commit()

    async def delete(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeIdRequest,
    ) -> None:
        team_id = self._team_id(user)
        kb = await knowledge_repo.get_by_id_and_team(db, body.id, team_id)
        if not kb:
            raise NotFoundError("知识库不存在")

        # 先清向量；失败则抛错，不执行下方 delete / commit
        #await vector_repo.delete_by_knowledge_base(team_id, kb.id)
        await knowledge_repo.delete(db, kb)
        await db.commit()

    async def list_knowledge_bases(
        self,
        db: AsyncSession,
        user: dict[str, Any],
    ) -> list:
        """兼容旧调用。"""
        items, _ = await knowledge_repo.page_by_team(
            db, self._team_id(user), page=1, page_size=1000
        )
        return [_to_item(kb) for kb in items]

    async def create_document(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        *,
        kb_id: int,
        file: UploadFile,
    ) -> DocumentCreateData:
        """上传文档：落盘后按策略解析全文并写入 documents.full_text。

        流程：uploading → 存盘 → parsing → completed（失败则为 failed）。
        切片与向量化后续再做。
        """
        team_id = self._team_id(user)
        kb = await knowledge_repo.get_by_id_and_team(db, kb_id, team_id)
        if not kb:
            raise NotFoundError("知识库不存在")

        file_type = resolve_file_type(file.filename)
        if not file_type:
            raise AppException(
                code=40001,
                message="不支持的文件类型，仅支持 pdf/docx/md/txt",
                status_code=400,
            )

        content = await file.read()
        if not content:
            raise AppException(code=40002, message="文件内容为空", status_code=400)
        if len(content) > settings.upload_max_bytes:
            max_mb = settings.upload_max_bytes // (1024 * 1024)
            raise AppException(
                code=40003,
                message=f"文件过大，最大允许 {max_mb}MB",
                status_code=400,
            )

        title = title_from_filename(file.filename)
        relative_path = build_relative_path(team_id, kb_id, file.filename)

        doc = await document_repo.create(
            db,
            knowledge_base_id=kb_id,
            title=title,
            file_type=file_type,
            file_path=relative_path,
            file_size=0,
            status=DocumentStatus.uploading,
        )
        await db.commit()

        try:
            file_size = await save_upload_file(relative_path, content)
            await document_repo.update_file_meta(
                db,
                doc,
                file_size=file_size,
                status=DocumentStatus.parsing,
            )
            await db.commit()
        except Exception:
            await document_repo.update_file_meta(
                db, doc, status=DocumentStatus.failed
            )
            await db.commit()
            raise AppException(
                code=50001, message="文件保存失败", status_code=500
            ) from None

        try:
            full_text = await parse_document(relative_path, file_type)
            await document_repo.update_file_meta(
                db,
                doc,
                full_text=full_text,
                set_full_text=True,
                status=DocumentStatus.completed,
            )
            await db.commit()

            # 后续开发：切块 / Embedding / 写入 Milvus
            # await document_chunk_service.chunk_and_embed(doc.id)

        except DocumentParseError as exc:
            await document_repo.update_file_meta(
                db, doc, status=DocumentStatus.failed
            )
            await db.commit()
            raise AppException(
                code=40004, message=exc.message, status_code=400
            ) from None
        except Exception:
            await document_repo.update_file_meta(
                db, doc, status=DocumentStatus.failed
            )
            await db.commit()
            raise AppException(
                code=50002, message="文档解析失败", status_code=500
            ) from None

        return DocumentCreateData(id=doc.id)

    async def get_document_by_id(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: DocumentIdRequest,
    ) -> DocumentItem:
        doc = await document_repo.get_by_id_and_team(
            db, body.document_id, self._team_id(user)
        )
        if not doc:
            raise NotFoundError("文档不存在")
        return _to_document_item(doc, include_full_text=True)

    async def page_documents(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: DocumentPageRequest,
    ) -> DocumentPageData:
        team_id = self._team_id(user)
        kb = await knowledge_repo.get_by_id_and_team(db, body.kb_id, team_id)
        if not kb:
            raise NotFoundError("知识库不存在")

        keyword = body.keyword.strip() if body.keyword else None
        items, total = await document_repo.page_by_kb(
            db,
            knowledge_base_id=body.kb_id,
            team_id=team_id,
            page=body.page,
            page_size=body.page_size,
            keyword=keyword or None,
        )
        return DocumentPageData(
            items=[_to_document_item(doc) for doc in items],
            total=total,
            page=body.page,
        )

    async def delete_document_by_id(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: DocumentIdRequest,
    ) -> None:
        doc = await document_repo.get_by_id_and_team(
            db, body.document_id, self._team_id(user)
        )
        if not doc:
            raise NotFoundError("文档不存在")
        await document_repo.soft_delete(db, doc)
        await db.commit()


knowledge_service = KnowledgeService()
