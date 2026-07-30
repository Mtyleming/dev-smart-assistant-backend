"""团队数据访问。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import Team


class TeamRepository:
    """团队表 CRUD 封装。"""

    async def create(self, db: AsyncSession, name: str) -> Team:
        """创建团队记录，id 由数据库自增生成。"""
        team = Team(name=name)
        db.add(team)
        await db.flush()
        return team


team_repo = TeamRepository()
