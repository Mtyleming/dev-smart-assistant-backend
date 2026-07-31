"""团队数据访问。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.base_models import Team, TeamMember


class TeamRepository:
    """团队表 CRUD 封装。"""

    async def create(
        self,
        db: AsyncSession,
        name: str,
        description: str | None = None,
    ) -> Team:
        """创建团队记录，id 由数据库自增生成。"""
        team = Team(name=name, description=description)
        db.add(team)
        await db.flush()
        return team

    async def get_by_id(self, db: AsyncSession, team_id: int) -> Team | None:
        """按 ID 查询未解散的团队。"""
        result = await db.execute(
            select(Team).where(Team.id == team_id, Team.is_delete.is_(False))
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, db: AsyncSession, name: str) -> Team | None:
        """按名称查询团队。"""
        result = await db.execute(select(Team).where(Team.name == name))
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        team: Team,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Team:
        """更新团队信息。"""
        if name is not None:
            team.name = name
        if description is not None:
            team.description = description
        await db.flush()
        return team

    async def dissolve(self, db: AsyncSession, team: Team) -> None:
        """软删除团队（解散）。"""
        team.is_delete = True
        await db.flush()

    async def list_active_with_members(self, db: AsyncSession) -> list[Team]:
        """查询所有未解散团队及其成员（含用户信息）。"""
        result = await db.execute(
            select(Team)
            .options(joinedload(Team.members).joinedload(TeamMember.user))
            .where(Team.is_delete.is_(False))
            .order_by(Team.created_at.asc())
        )
        return list(result.scalars().unique().all())


team_repo = TeamRepository()
