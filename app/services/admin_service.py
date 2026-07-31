"""超级管理员业务逻辑。"""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.super_admin import is_super_admin
from app.models.base_models import TeamMember
from app.repositories.cache_repo import cache_repo
from app.repositories.team_repo import team_repo
from app.repositories.user_repo import user_repo
from app.schemas.admin import (
    ROLE_SORT_ORDER,
    AdminOrganizationTree,
    AdminTeamNode,
    AdminUserNode,
    UpdateUserStatusRequest,
)


class AdminService:
    """超级管理员：组织树查询与用户状态管理。"""

    def _to_user_node(self, member: TeamMember) -> AdminUserNode:
        """将团队成员关系转为树节点。"""
        user = member.user
        return AdminUserNode(
            id=user.id,
            username=user.username,
            email=user.email,
            role=member.role.value,
            is_active=user.is_active,
            is_super_admin=is_super_admin(user.id),
        )

    def _to_unassigned_node(self, user) -> AdminUserNode:
        """将未入团用户转为树节点。"""
        return AdminUserNode(
            id=user.id,
            username=user.username,
            email=user.email,
            role="",
            is_active=user.is_active,
            is_super_admin=is_super_admin(user.id),
        )

    def _sort_members(self, members: list[TeamMember]) -> list[TeamMember]:
        """按 admin → tech_lead → developer 顺序排序。"""
        return sorted(
            members,
            key=lambda member: (
                ROLE_SORT_ORDER.get(member.role, 99),
                member.created_at,
            ),
        )

    async def get_organization_tree(
        self, db: AsyncSession
    ) -> AdminOrganizationTree:
        """获取按团队分组、成员按角色排序的组织树。"""
        teams = await team_repo.list_active_with_members(db)
        team_nodes = [
            AdminTeamNode(
                id=team.id,
                name=team.name,
                description=team.description,
                member_count=len(team.members),
                members=[
                    self._to_user_node(member)
                    for member in self._sort_members(team.members)
                ],
            )
            for team in teams
        ]

        unassigned = await user_repo.list_unassigned(db)
        return AdminOrganizationTree(
            teams=team_nodes,
            unassigned_users=[
                self._to_unassigned_node(user) for user in unassigned
            ],
        )

    async def update_user_status(
        self,
        db: AsyncSession,
        redis: Redis | None,
        operator_user_id: str,
        target_user_id: int,
        payload: UpdateUserStatusRequest,
    ) -> None:
        """启用或停用用户；停用时清除其登录会话。"""
        if int(operator_user_id) == target_user_id and not payload.is_active:
            raise ConflictError("不能停用自己的账号")

        user = await user_repo.get_by_id(db, target_user_id)
        if not user:
            raise NotFoundError("用户不存在")

        if user.is_active == payload.is_active:
            return

        await user_repo.update_is_active(db, user, payload.is_active)
        await db.commit()

        if not payload.is_active and redis is not None:
            await cache_repo.delete_login_session(redis, str(target_user_id))


admin_service = AdminService()
