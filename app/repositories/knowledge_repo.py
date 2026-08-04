"""知识库数据访问。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import KnowledgeBase


class KnowledgeRepository:
    """知识库表 CRUD 封装。"""

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        description: str | None,
        team_id: int,
        created_by: int,
    ) -> KnowledgeBase:
        """创建知识库并 flush 拿到自增 ID。"""
        kb = KnowledgeBase(
            name=name,
            description=description,
            team_id=team_id,
            created_by=created_by,
        )
        db.add(kb)
        await db.flush()
        await db.refresh(kb)
        return kb

    async def get_by_id_and_team(
        self, db: AsyncSession, kb_id: int, team_id: int
    ) -> KnowledgeBase | None:
        """按 ID + 团队查询（跨团队视为不存在）。"""
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.team_id == team_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_team_and_name(
        self,
        db: AsyncSession,
        team_id: int,
        name: str,
        *,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
        """同团队按名称查重；exclude_id 用于更新时排除自身。"""
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.team_id == team_id,
            KnowledgeBase.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(KnowledgeBase.id != exclude_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def page_by_team(
        self,
        db: AsyncSession,
        team_id: int,
        *,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[KnowledgeBase], int]:
        """分页列出团队知识库，按 updated_at 降序。"""
        filters = [KnowledgeBase.team_id == team_id]
        if keyword:
            filters.append(KnowledgeBase.name.like(f"%{keyword}%"))

        count_result = await db.execute(
            select(func.count()).select_from(KnowledgeBase).where(*filters)
        )
        total = int(count_result.scalar_one())

        result = await db.execute(
            select(KnowledgeBase)
            .where(*filters)
            .order_by(KnowledgeBase.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        db: AsyncSession,
        kb: KnowledgeBase,
        *,
        name: str | None = None,
        description: str | None = None,
        set_description: bool = False,
    ) -> KnowledgeBase:
        """更新字段；set_description=True 时允许把 description 写成 None。"""
        if name is not None:
            kb.name = name
        if set_description:
            kb.description = description
        await db.flush()
        await db.refresh(kb)
        return kb

    async def delete(self, db: AsyncSession, kb: KnowledgeBase) -> None:
        """物理删除知识库记录。"""
        await db.delete(kb)
        await db.flush()

    async def list_by_team(self, db: AsyncSession, team_id: int) -> list[KnowledgeBase]:
        """列出团队下的知识库（保留给兼容调用）。"""
        items, _ = await self.page_by_team(db, team_id, page=1, page_size=1000)
        return items

    async def count_by_team(self, db: AsyncSession, team_id: int) -> int:
        """统计团队关联的知识库数量。"""
        result = await db.execute(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.team_id == team_id)
        )
        return int(result.scalar_one())


knowledge_repo = KnowledgeRepository()
