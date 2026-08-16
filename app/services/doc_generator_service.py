"""文档生成业务：模板 CRUD + 生成/导出编排。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.base_models import DocumentTemplate, DocumentTemplateType
from app.repositories.document_template_repo import document_template_repo
from app.schemas.docs import (
    DocExportRequest,
    DocGenerateData,
    DocGenerateRequest,
    TemplateCreateData,
    TemplateCreateRequest,
    TemplateItem,
    TemplateUpdateRequest,
)
from app.templateDoc.template import document_generation_service

logger = logging.getLogger(__name__)


def _to_item(tmpl: DocumentTemplate) -> TemplateItem:
    type_value = tmpl.type.value if hasattr(tmpl.type, "value") else str(tmpl.type)
    return TemplateItem(
        id=tmpl.id,
        name=tmpl.name,
        type=type_value,
        content=tmpl.content,
        team_id=tmpl.team_id,
        is_builtin=bool(tmpl.is_builtin),
        version=int(tmpl.version or 1),
        created_by=tmpl.created_by,
        created_at=tmpl.created_at,
        updated_at=tmpl.updated_at,
    )


class DocGeneratorService:
    """文档生成与模板管理。"""

    @staticmethod
    def _team_id(user: dict[str, Any]) -> int:
        return int(user["team_id"])

    @staticmethod
    def _user_id(user: dict[str, Any]) -> int:
        return int(user["id"])

    async def generate(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: DocGenerateRequest,
    ) -> DocGenerateData:
        """提交输入内容，返回带 AI 声明头的 Markdown。"""
        team_id = self._team_id(user)
        kb_ids = [int(body.knowledge_base_id)] if body.knowledge_base_id else None
        result = await document_generation_service.generate(
            db,
            body.doc_type,
            body.input_content,
            team_id,
            is_code=body.is_code,
            kb_ids=kb_ids,
            template_id=body.template_id,
        )
        return DocGenerateData(**result)

    async def export(self, body: DocExportRequest) -> tuple[bytes, str, str]:
        """导出文件字节、Content-Type、下载文件名。"""
        from datetime import datetime

        raw = await document_generation_service.export(
            body.content, body.format, body.doc_type
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_type = (body.doc_type or "document").strip() or "document"
        if body.format == "html":
            media = "text/html; charset=utf-8"
            filename = f"{safe_type}_{timestamp}.html"
        elif body.format == "pdf":
            media = "application/pdf"
            filename = f"{safe_type}_{timestamp}.pdf"
        else:
            media = "text/markdown; charset=utf-8"
            filename = f"{safe_type}_{timestamp}.md"
        return raw, media, filename

    async def list_templates(
        self, db: AsyncSession, user: dict[str, Any]
    ) -> list[TemplateItem]:
        """当前团队自定义模板 + 系统内置模板。"""
        team_id = self._team_id(user)
        rows = await document_template_repo.list_visible(db, team_id)
        return [_to_item(row) for row in rows]

    async def create_template(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: TemplateCreateRequest,
    ) -> TemplateCreateData:
        """创建自定义模板（admin / tech_lead）。"""
        team_id = self._team_id(user)
        exists = await document_template_repo.get_by_team_and_name(
            db, team_id, body.name
        )
        if exists:
            raise ConflictError("同团队已存在同名模板")

        try:
            tmpl = await document_template_repo.create(
                db,
                name=body.name,
                doc_type=body.type,
                content=body.content,
                team_id=team_id,
                created_by=self._user_id(user),
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            logger.warning(
                "创建模板命中唯一约束 team_id=%s name=%s: %s",
                team_id,
                body.name,
                exc,
            )
            raise ConflictError("同团队已存在同名模板") from exc
        logger.info(
            "已创建文档模板 id=%s team_id=%s type=%s user_id=%s",
            tmpl.id,
            team_id,
            body.type.value,
            self._user_id(user),
        )
        return TemplateCreateData(id=tmpl.id, version=int(tmpl.version or 1))

    async def update_template(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        template_id: int,
        body: TemplateUpdateRequest,
    ) -> TemplateItem:
        """更新自定义模板并递增版本。"""
        team_id = self._team_id(user)
        tmpl = await self._require_writable_template(db, template_id, team_id)
        fields = body.model_fields_set
        new_name = body.name if "name" in fields else None
        if new_name:
            dup = await document_template_repo.get_by_team_and_name(
                db, team_id, new_name, exclude_id=tmpl.id
            )
            if dup:
                raise ConflictError("同团队已存在同名模板")

        new_type: DocumentTemplateType | None = (
            body.type if "type" in fields else None
        )
        new_content = body.content if "content" in fields else None
        try:
            tmpl = await document_template_repo.update(
                db,
                tmpl,
                name=new_name,
                doc_type=new_type,
                content=new_content,
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            logger.warning(
                "更新模板命中唯一约束 id=%s team_id=%s name=%s: %s",
                template_id,
                team_id,
                new_name,
                exc,
            )
            raise ConflictError("同团队已存在同名模板") from exc
        logger.info(
            "已更新文档模板 id=%s team_id=%s version=%s",
            tmpl.id,
            team_id,
            tmpl.version,
        )
        return _to_item(tmpl)

    async def delete_template(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        template_id: int,
    ) -> None:
        """删除自定义模板。"""
        team_id = self._team_id(user)
        tmpl = await self._require_writable_template(db, template_id, team_id)
        await document_template_repo.delete(db, tmpl)
        await db.commit()
        logger.info("已删除文档模板 id=%s team_id=%s", template_id, team_id)

    async def _require_writable_template(
        self, db: AsyncSession, template_id: int, team_id: int
    ) -> DocumentTemplate:
        """仅允许操作本团队自定义模板；内置模板不可改删。"""
        row = await document_template_repo.get_by_id(db, template_id)
        if row is None:
            raise NotFoundError("模板不存在")
        if row.is_builtin or row.team_id is None:
            raise ForbiddenError("系统内置模板不可修改或删除")
        if int(row.team_id) != team_id:
            # 跨团队不暴露存在性
            raise NotFoundError("模板不存在")
        return row


doc_generator_service = DocGeneratorService()
