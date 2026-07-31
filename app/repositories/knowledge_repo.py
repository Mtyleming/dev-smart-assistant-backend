"""知识库数据访问。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import KnowledgeBase


class KnowledgeRepository:
    """知识库表 CRUD 封装。"""

    async def list_by_team(self, db: AsyncSession, team_id: int) -> list[KnowledgeBase]:
        """列出团队下的知识库。"""
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.team_id == team_id)
        )
        return list(result.scalars().all())

    async def count_by_team(self, db: AsyncSession, team_id: int) -> int:
        """统计团队关联的知识库数量。"""
        result = await db.execute(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.team_id == team_id)
        )
        return int(result.scalar_one())


knowledge_repo = KnowledgeRepository()
