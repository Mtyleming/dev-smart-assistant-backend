"""邀请入团与审批相关请求与响应模型。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.base_models import TeamMemberRole


class InviteCodeData(BaseModel):
    """生成的邀请码信息。"""

    invite_code: str
    expires_at: datetime
    team_id: int


class JoinTeamRequest(BaseModel):
    """使用邀请码申请加入团队。"""

    invite_code: str = Field(..., min_length=1, description="邀请码")


class JoinTeamData(BaseModel):
    """申请加入团队成功后的数据。"""

    request_id: str
    team_id: int
    team_name: str
    status: str = "pending"


class JoinRequestData(BaseModel):
    """待审批的入团申请。"""

    request_id: str
    user_id: int
    username: str
    created_at: str
    status: str


class ApproveJoinRequest(BaseModel):
    """审批通过时指定成员角色。"""

    role: TeamMemberRole = Field(..., description="新成员角色")
