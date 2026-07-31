"""团队相关请求与响应模型。"""

from pydantic import BaseModel, Field

from app.models.base_models import TeamMemberRole


class TeamCreateRequest(BaseModel):
    """创建团队请求体。"""

    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    description: str | None = Field(default=None, description="团队描述")


class TeamUpdateRequest(BaseModel):
    """更新团队请求体。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class TeamBriefData(BaseModel):
    """团队简要信息。"""

    id: int
    name: str


class UserTeamData(BaseModel):
    """当前用户所属团队（用于切换团队）。"""

    id: int
    name: str
    role: str
    is_current: bool = Field(..., description="是否为 Token 中的当前团队")


class TeamDetailData(BaseModel):
    """团队详情。"""

    id: int
    name: str
    description: str | None
    member_count: int


class TeamMemberData(BaseModel):
    """团队成员信息。"""

    id: int
    username: str
    role: str


class AssignMemberRoleRequest(BaseModel):
    """分配成员角色请求体。"""

    role: TeamMemberRole = Field(..., description="新角色：admin / tech_lead / developer")
