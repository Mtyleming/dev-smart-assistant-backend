"""文档模板数据访问：按 team_id 隔离，支持版本快照。"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import (
    DocumentTemplate,
    DocumentTemplateType,
    DocumentTemplateVersion,
)


class DocumentTemplateRepository:
    """document_templates / document_template_versions CRUD。"""

    async def get_by_id(
        self, db: AsyncSession, template_id: int
    ) -> DocumentTemplate | None:
        """按主键查询模板（不限团队）。"""
        result = await db.execute(
            select(DocumentTemplate).where(DocumentTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_team(
        self, db: AsyncSession, template_id: int, team_id: int
    ) -> DocumentTemplate | None:
        """按 ID + 当前团队查询自定义模板（跨团队视为不存在）。"""
        result = await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.id == template_id,
                DocumentTemplate.team_id == team_id,
                DocumentTemplate.is_builtin.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_visible_by_id(
        self, db: AsyncSession, template_id: int, team_id: int
    ) -> DocumentTemplate | None:
        """当前团队可见的指定模板：本团队自定义，或系统内置。"""
        result = await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.id == template_id,
                or_(
                    DocumentTemplate.team_id == team_id,
                    DocumentTemplate.is_builtin.is_(True),
                ),
            )
        )
        return result.scalar_one_or_none()

    async def count_custom_by_type(
        self,
        db: AsyncSession,
        team_id: int,
        doc_type: str | DocumentTemplateType,
    ) -> int:
        """统计某团队某类型的自定义模板数量（用于多模板时打日志）。"""
        type_value = (
            doc_type.value if isinstance(doc_type, DocumentTemplateType) else str(doc_type)
        )
        result = await db.execute(
            select(func.count())
            .select_from(DocumentTemplate)
            .where(
                DocumentTemplate.team_id == team_id,
                DocumentTemplate.type == type_value,
                DocumentTemplate.is_builtin.is_(False),
            )
        )
        return int(result.scalar_one() or 0)

    async def get_by_team_and_name(
        self,
        db: AsyncSession,
        team_id: int,
        name: str,
        *,
        exclude_id: int | None = None,
    ) -> DocumentTemplate | None:
        """同团队按名称查重；exclude_id 用于更新时排除自身。"""
        stmt = select(DocumentTemplate).where(
            DocumentTemplate.team_id == team_id,
            DocumentTemplate.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(DocumentTemplate.id != exclude_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_template(
        self,
        db: AsyncSession,
        team_id: int,
        doc_type: str | DocumentTemplateType,
    ) -> DocumentTemplate | None:
        """加载生成用模板：优先团队自定义，其次库内系统内置。

        同一类型有多份自定义时取最近更新的一份。
        """
        type_value = (
            doc_type.value if isinstance(doc_type, DocumentTemplateType) else str(doc_type)
        )
        custom_result = await db.execute(
            select(DocumentTemplate)
            .where(
                DocumentTemplate.team_id == team_id,
                DocumentTemplate.type == type_value,
                DocumentTemplate.is_builtin.is_(False),
            )
            .order_by(DocumentTemplate.updated_at.desc(), DocumentTemplate.id.desc())
            .limit(1)
        )
        custom = custom_result.scalar_one_or_none()
        if custom:
            return custom

        builtin_result = await db.execute(
            select(DocumentTemplate)
            .where(
                DocumentTemplate.is_builtin.is_(True),
                DocumentTemplate.type == type_value,
                DocumentTemplate.team_id.is_(None),
            )
            .order_by(DocumentTemplate.id.asc())
            .limit(1)
        )
        return builtin_result.scalar_one_or_none()

    async def list_visible(
        self, db: AsyncSession, team_id: int
    ) -> list[DocumentTemplate]:
        """当前团队可见模板：本团队自定义 + 系统内置。"""
        result = await db.execute(
            select(DocumentTemplate)
            .where(
                or_(
                    DocumentTemplate.team_id == team_id,
                    DocumentTemplate.is_builtin.is_(True),
                )
            )
            .order_by(
                DocumentTemplate.is_builtin.asc(),
                DocumentTemplate.updated_at.desc(),
                DocumentTemplate.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        doc_type: DocumentTemplateType,
        content: str,
        team_id: int,
        created_by: int,
    ) -> DocumentTemplate:
        """创建团队自定义模板，初始版本为 1。"""
        tmpl = DocumentTemplate(
            name=name,
            type=doc_type,
            content=content,
            team_id=team_id,
            is_builtin=False,
            created_by=created_by,
            version=1,
        )
        db.add(tmpl)
        await db.flush()
        await db.refresh(tmpl)
        return tmpl

    async def archive_current_version(
        self, db: AsyncSession, tmpl: DocumentTemplate
    ) -> DocumentTemplateVersion:
        """把当前模板内容写入历史表，供版本回溯。"""
        snapshot = DocumentTemplateVersion(
            template_id=tmpl.id,
            version=int(tmpl.version or 1),
            name=tmpl.name,
            type=tmpl.type,
            content=tmpl.content,
            team_id=tmpl.team_id,
            created_by=tmpl.created_by,
        )
        db.add(snapshot)
        await db.flush()
        return snapshot

    async def update(
        self,
        db: AsyncSession,
        tmpl: DocumentTemplate,
        *,
        name: str | None = None,
        doc_type: DocumentTemplateType | None = None,
        content: str | None = None,
    ) -> DocumentTemplate:
        """更新自定义模板：先归档旧版本，再写入新内容并递增 version。"""
        await self.archive_current_version(db, tmpl)
        if name is not None:
            tmpl.name = name
        if doc_type is not None:
            tmpl.type = doc_type
        if content is not None:
            tmpl.content = content
        tmpl.version = int(tmpl.version or 1) + 1
        await db.flush()
        await db.refresh(tmpl)
        return tmpl

    async def delete(self, db: AsyncSession, tmpl: DocumentTemplate) -> None:
        """删除自定义模板（历史快照随外键 CASCADE 清理）。"""
        await db.delete(tmpl)
        await db.flush()


document_template_repo = DocumentTemplateRepository()
# 兼容 templateDoc 草稿中的类名
DocumentTemplateRepo = DocumentTemplateRepository
