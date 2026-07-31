"""团队业务逻辑。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.base_models import TeamMemberRole
from app.repositories.knowledge_repo import knowledge_repo
from app.repositories.team_member_repo import team_member_repo
from app.repositories.team_repo import team_repo
from app.schemas.team import (
    AssignMemberRoleRequest,
    TeamBriefData,
    TeamCreateRequest,
    TeamDetailData,
    TeamMemberData,
    TeamUpdateRequest,
    UserTeamData,
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

    async def list_my_teams(
        self,
        db: AsyncSession,
        user_id: str,
        current_team_id: str,
    ) -> list[UserTeamData]:
        """获取当前用户加入的团队列表（用于切换团队）。"""
        memberships = await team_member_repo.list_by_user(db, int(user_id))
        current_id = int(current_team_id)
        return [
            UserTeamData(
                id=member.team.id,
                name=member.team.name,
                role=member.role.value,
                is_current=member.team.id == current_id,
            )
            for member in memberships
        ]

    async def get_team_detail(
        self,
        db: AsyncSession,
        team_id: int,
        user_id: str,
    ) -> TeamDetailData:
        """获取团队详情（路由层已校验团队成员）。"""
        _ = user_id

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
        """更新团队信息（路由层已校验 admin）。"""
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
        """解散团队（路由层已校验 admin，软删除）。"""
        _ = user_id
        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        kb_count = await knowledge_repo.count_by_team(db, team_id)
        if kb_count > 0:
            raise ConflictError("请先清理团队关联的知识库数据")

        await team_repo.dissolve(db, team)
        await team_member_repo.delete_by_team(db, team_id)
        await db.commit()

    async def assign_member_role(
        self,
        db: AsyncSession,
        team_id: int,
        target_user_id: int,
        operator_user_id: str,
        payload: AssignMemberRoleRequest,
    ) -> None:
        """分配成员角色（路由层已校验 admin；转让 admin 时原 admin 降为 developer）。"""
        operator_id = int(operator_user_id)

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        target_membership = await team_member_repo.get_membership(
            db, team_id, target_user_id
        )
        if not target_membership:
            raise NotFoundError("成员不存在")

        new_role = payload.role
        if target_membership.role == new_role:
            return

        if new_role == TeamMemberRole.admin:
            if target_user_id == operator_id:
                return
            operator_membership = await team_member_repo.get_membership(
                db, team_id, operator_id
            )
            await team_member_repo.update_role(
                db, target_membership, TeamMemberRole.admin
            )
            if operator_membership:
                await team_member_repo.update_role(
                    db, operator_membership, TeamMemberRole.developer
                )
        elif target_membership.role == TeamMemberRole.admin:
            raise ConflictError("请先转让管理员权限")
        else:
            await team_member_repo.update_role(db, target_membership, new_role)

        await db.commit()

    async def remove_member(
        self,
        db: AsyncSession,
        team_id: int,
        target_user_id: int,
        operator_user_id: str,
    ) -> None:
        """从团队移除成员（路由层已校验 admin；不可移除唯一管理员）。"""
        _ = operator_user_id

        team = await team_repo.get_by_id(db, team_id)
        if not team:
            raise NotFoundError("团队不存在")

        target_membership = await team_member_repo.get_membership(
            db, team_id, target_user_id
        )
        if not target_membership:
            raise NotFoundError("成员不存在")

        if target_membership.role == TeamMemberRole.admin:
            raise ConflictError("请先转让管理员权限后再移除")

        await team_member_repo.delete_member(db, team_id, target_user_id)
        await db.commit()

    async def list_members(
        self,
        db: AsyncSession,
        team_id: int,
        user_id: str,
    ) -> list[TeamMemberData]:
        """获取团队成员列表（路由层已校验团队成员）。"""
        _ = user_id

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


team_service = TeamService()
