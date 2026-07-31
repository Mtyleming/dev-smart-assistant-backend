"""团队成员数据访问。"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.base_models import Team, TeamMember, TeamMemberRole


class TeamMemberRepository:
    """team_members 表 CRUD 封装。"""

    async def create(
        self,
        db: AsyncSession,
        *,
        team_id: int,
        user_id: int,
        role: TeamMemberRole,
    ) -> TeamMember:
        """创建团队成员关系。"""
        member = TeamMember(team_id=team_id, user_id=user_id, role=role)
        db.add(member)
        await db.flush()
        return member

    async def get_membership(
        self, db: AsyncSession, team_id: int, user_id: int
    ) -> TeamMember | None:
        """查询用户在指定团队的成员关系。"""
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_default_membership(
        self, db: AsyncSession, user_id: int
    ) -> TeamMember | None:
        """获取用户默认团队（最早加入的一个）。"""
        result = await db.execute(
            select(TeamMember)
            .where(TeamMember.user_id == user_id)
            .order_by(TeamMember.created_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_by_team(self, db: AsyncSession, team_id: int) -> int:
        """统计团队成员数量。"""
        result = await db.execute(
            select(func.count())
            .select_from(TeamMember)
            .where(TeamMember.team_id == team_id)
        )
        return int(result.scalar_one())

    async def list_members(self, db: AsyncSession, team_id: int) -> list[TeamMember]:
        """获取团队成员列表（含用户信息）。"""
        result = await db.execute(
            select(TeamMember)
            .options(joinedload(TeamMember.user))
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.created_at.asc())
        )
        return list(result.scalars().unique().all())

    async def list_by_user(
        self, db: AsyncSession, user_id: int
    ) -> list[TeamMember]:
        """获取用户加入的团队列表（不含已解散团队）。"""
        result = await db.execute(
            select(TeamMember)
            .options(joinedload(TeamMember.team))
            .join(Team, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user_id, Team.is_delete.is_(False))
            .order_by(TeamMember.created_at.asc())
        )
        return list(result.scalars().unique().all())

    async def delete_by_team(self, db: AsyncSession, team_id: int) -> None:
        """删除团队下所有成员关系。"""
        await db.execute(delete(TeamMember).where(TeamMember.team_id == team_id))

    async def delete_member(
        self, db: AsyncSession, team_id: int, user_id: int
    ) -> None:
        """删除指定团队成员关系。"""
        await db.execute(
            delete(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )

    async def update_role(
        self, db: AsyncSession, member: TeamMember, role: TeamMemberRole
    ) -> TeamMember:
        """更新成员角色。"""
        member.role = role
        await db.flush()
        return member

    async def count_admins_by_team(self, db: AsyncSession, team_id: int) -> int:
        """统计团队管理员数量。"""
        result = await db.execute(
            select(func.count())
            .select_from(TeamMember)
            .where(
                TeamMember.team_id == team_id,
                TeamMember.role == TeamMemberRole.admin,
            )
        )
        return int(result.scalar_one())


team_member_repo = TeamMemberRepository()
