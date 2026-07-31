"""团队业务逻辑。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.base_models import TeamMemberRole
from app.repositories.team_member_repo import team_member_repo
from app.repositories.team_repo import team_repo
from app.schemas.team import (
    TeamBriefData,
    TeamCreateRequest,
    TeamDetailData,
    TeamMemberData,
    TeamUpdateRequest,
)


class TeamService:
    """团队增删改查。"""

    async def create_team(
        self,
        db: AsyncSession,
        user_id: str,
        payload: TeamCreateRequest,
    ) -> TeamBriefData:
        """创建团队，创建者自动成为 admin。"""
        existing = await team_repo.get_by_name(db, payload.name)
        if existing and not existing.is_delete:
            raise ConflictError("团队名称已存在")

        team = await team_repo.create(db, payload.name, payload.description)
        await team_member_repo.create(
            db,
            team_id=team.id,
            user_id=int(user_id),
            role=TeamMemberRole.admin,
        )
        await db.commit()
        await db.refresh(team)
        return TeamBriefData(id=team.id, name=team.name)

    async def get_team_detail(
        self,
        db: AsyncSession,
        team_id: int,
        user_id: str,
    ) -> TeamDetailData:
        """获取团队详情（需为团队成员）。"""
        await self._ensure_member(db, team_id, user_id)

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        member_count = await team_member_repo.count_by_team(db, team_id)
        return TeamDetailData(
            id=team.id,
            name=team.name,
            description=team.description,
            member_count=member_count,
        )

    async def update_team(
        self,
        db: AsyncSession,
        team_id: int,
        user_id: str,
        payload: TeamUpdateRequest,
    ) -> TeamBriefData:
        """更新团队信息（仅 admin）。"""
        await self._ensure_admin(db, team_id, user_id)

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        if payload.name and payload.name != team.name:
            existing = await team_repo.get_by_name(db, payload.name)
            if existing and existing.id != team_id and not existing.is_delete:
                raise ConflictError("团队名称已存在")

        team = await team_repo.update(
            db,
            team,
            name=payload.name,
            description=payload.description,
        )
        await db.commit()
        await db.refresh(team)
        return TeamBriefData(id=team.id, name=team.name)

    async def dissolve_team(
        self,
        db: AsyncSession,
        team_id: int,
        user_id: str,
    ) -> None:
        """解散团队（仅 admin，软删除）。"""
        await self._ensure_admin(db, team_id, user_id)

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        await team_repo.dissolve(db, team)
        await team_member_repo.delete_by_team(db, team_id)
        await db.commit()

    async def list_members(
        self,
        db: AsyncSession,
        team_id: int,
        user_id: str,
    ) -> list[TeamMemberData]:
        """获取团队成员列表（需为团队成员）。"""
        await self._ensure_member(db, team_id, user_id)

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        members = await team_member_repo.list_members(db, team_id)
        return [
            TeamMemberData(
                id=member.user.id,
                username=member.user.username,
                role=member.role.value,
            )
            for member in members
        ]

    async def _ensure_member(
        self, db: AsyncSession, team_id: int, user_id: str
    ) -> None:
        membership = await team_member_repo.get_membership(
            db, team_id, int(user_id)
        )
        if not membership:
            raise ForbiddenError("无权访问该团队")

    async def _ensure_admin(
        self, db: AsyncSession, team_id: int, user_id: str
    ) -> None:
        membership = await team_member_repo.get_membership(
            db, team_id, int(user_id)
        )
        if not membership or membership.role != TeamMemberRole.admin:
            raise ForbiddenError("仅管理员可操作")


team_service = TeamService()
