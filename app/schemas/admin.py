"""超级管理员相关请求与响应模型。"""

from pydantic import BaseModel, Field

from app.models.base_models import TeamMemberRole


class AdminUserNode(BaseModel):
    """组织树中的用户节点。"""

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    is_super_admin: bool


class AdminTeamNode(BaseModel):
    """组织树中的团队节点。"""

    id: int
    name: str
    description: str | None
    member_count: int
    members: list[AdminUserNode]


class AdminOrganizationTree(BaseModel):
    """按团队分组的组织树。"""

    teams: list[AdminTeamNode]
    unassigned_users: list[AdminUserNode] = Field(
        default_factory=list,
        description="未加入任何团队的用户",
    )


class UpdateUserStatusRequest(BaseModel):
    """启用/停用用户请求体。"""

    is_active: bool = Field(..., description="true 启用，false 停用")


ROLE_SORT_ORDER: dict[TeamMemberRole, int] = {
    TeamMemberRole.admin: 0,
    TeamMemberRole.tech_lead: 1,
    TeamMemberRole.developer: 2,
}
