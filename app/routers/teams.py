"""团队模块路由：/api/v1/teams。"""

from fastapi import APIRouter

from app.core.config import settings
from app.dependencies import CurrentUser, DbSession, RedisClient, TeamAdminUser, TeamMemberUser
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.invitation import (
    ApproveJoinRequest,
    InviteCodeData,
    JoinRequestData,
    JoinTeamData,
    JoinTeamRequest,
)
from app.schemas.team import (
    AssignMemberRoleRequest,
    TeamBriefData,
    TeamCreateRequest,
    TeamDetailData,
    TeamMemberData,
    TeamUpdateRequest,
    UserTeamData,
)
from app.services.invite_service import invite_service
from app.services.team_service import team_service

router = APIRouter(prefix=settings.api_v1_prefix + "/teams", tags=["团队"])


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def teams_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="teams", detail="团队管理路由已就绪")
    )


@router.post(
    "/join",
    response_model=ApiResponse[JoinTeamData],
    summary="申请加入团队",
    status_code=201,
)
async def join_team(
    body: JoinTeamRequest,
    db: DbSession,
    redis: RedisClient,
    user: CurrentUser,
) -> ApiResponse[JoinTeamData]:
    """使用邀请码申请加入团队，等待管理员审批。"""
    data = await invite_service.apply_to_join(db, redis, user["id"], body)
    return ApiResponse(data=data)


@router.post(
    "",
    response_model=ApiResponse[TeamBriefData],
    summary="创建团队",
    status_code=201,
)
async def create_team(
    body: TeamCreateRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[TeamBriefData]:
    """创建团队，当前用户自动成为 admin。"""
    data = await team_service.create_team(db, user["id"], body)
    return ApiResponse(data=data)


@router.get(
    "/mine",
    response_model=ApiResponse[list[UserTeamData]],
    summary="获取我的团队列表",
)
async def list_my_teams(
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[list[UserTeamData]]:
    """获取当前用户加入的团队列表，含各团队内角色及是否为当前团队。"""
    data = await team_service.list_my_teams(db, user["id"], user["team_id"])
    return ApiResponse(data=data)


@router.get(
    "/{team_id}",
    response_model=ApiResponse[TeamDetailData],
    summary="获取团队详情",
)
async def get_team(
    team_id: int,
    db: DbSession,
    user: TeamMemberUser,
) -> ApiResponse[TeamDetailData]:
    """获取团队详情，需为团队成员。"""
    data = await team_service.get_team_detail(db, team_id, user["id"])
    return ApiResponse(data=data)


@router.put(
    "/{team_id}",
    response_model=ApiResponse[TeamBriefData],
    summary="更新团队信息",
)
async def update_team(
    team_id: int,
    body: TeamUpdateRequest,
    db: DbSession,
    user: TeamAdminUser,
) -> ApiResponse[TeamBriefData]:
    """更新团队信息，仅 admin 可操作。"""
    data = await team_service.update_team(db, team_id, user["id"], body)
    return ApiResponse(data=data)


@router.delete(
    "/{team_id}",
    response_model=ApiResponse[None],
    summary="解散团队",
)
async def dissolve_team(
    team_id: int,
    db: DbSession,
    user: TeamAdminUser,
) -> ApiResponse[None]:
    """解散团队，仅 admin 可操作。"""
    await team_service.dissolve_team(db, team_id, user["id"])
    return ApiResponse(message="团队已解散")


@router.get(
    "/{team_id}/members",
    response_model=ApiResponse[list[TeamMemberData]],
    summary="获取团队成员列表",
)
async def list_team_members(
    team_id: int,
    db: DbSession,
    user: TeamMemberUser,
) -> ApiResponse[list[TeamMemberData]]:
    """获取团队成员列表，需为团队成员。"""
    data = await team_service.list_members(db, team_id, user["id"])
    return ApiResponse(data=data)


@router.put(
    "/{team_id}/members/{user_id}/role",
    response_model=ApiResponse[None],
    summary="分配成员角色",
)
async def assign_member_role(
    team_id: int,
    user_id: int,
    body: AssignMemberRoleRequest,
    db: DbSession,
    user: TeamAdminUser,
) -> ApiResponse[None]:
    """分配成员新角色，仅 admin 可操作；转让 admin 时原 admin 自动降为 developer。"""
    await team_service.assign_member_role(
        db, team_id, user_id, user["id"], body
    )
    return ApiResponse(message="角色已更新")


@router.delete(
    "/{team_id}/members/{user_id}",
    response_model=ApiResponse[None],
    summary="移除团队成员",
)
async def remove_team_member(
    team_id: int,
    user_id: int,
    db: DbSession,
    user: TeamAdminUser,
) -> ApiResponse[None]:
    """从团队移除成员，仅 admin 可操作；不可直接移除管理员。"""
    await team_service.remove_member(db, team_id, user_id, user["id"])
    return ApiResponse(message="成员已移除")


@router.post(
    "/{team_id}/invites",
    response_model=ApiResponse[InviteCodeData],
    summary="生成邀请码",
    status_code=201,
)
async def create_invite_code(
    team_id: int,
    db: DbSession,
    redis: RedisClient,
    user: TeamAdminUser,
) -> ApiResponse[InviteCodeData]:
    """生成 7 天有效的一次性邀请码，仅 admin 可操作。"""
    data = await invite_service.create_invite_code(
        db, redis, team_id, user["id"]
    )
    return ApiResponse(data=data)


@router.get(
    "/{team_id}/join-requests",
    response_model=ApiResponse[list[JoinRequestData]],
    summary="查看入团审批列表",
)
async def list_join_requests(
    team_id: int,
    db: DbSession,
    redis: RedisClient,
    user: TeamAdminUser,
) -> ApiResponse[list[JoinRequestData]]:
    """查看待审批的入团申请，仅 admin 可操作。"""
    data = await invite_service.list_join_requests(
        db, redis, team_id, user["id"]
    )
    return ApiResponse(data=data)


@router.post(
    "/{team_id}/join-requests/{request_id}/approve",
    response_model=ApiResponse[None],
    summary="审批通过入团申请",
)
async def approve_join_request(
    team_id: int,
    request_id: str,
    body: ApproveJoinRequest,
    db: DbSession,
    redis: RedisClient,
    user: TeamAdminUser,
) -> ApiResponse[None]:
    """审批通过入团申请并指定成员角色，仅 admin 可操作。"""
    await invite_service.approve_join_request(
        db, redis, team_id, request_id, user["id"], body
    )
    return ApiResponse(message="审批通过")


@router.post(
    "/{team_id}/join-requests/{request_id}/reject",
    response_model=ApiResponse[None],
    summary="拒绝入团申请",
)
async def reject_join_request(
    team_id: int,
    request_id: str,
    db: DbSession,
    redis: RedisClient,
    user: TeamAdminUser,
) -> ApiResponse[None]:
    """拒绝入团申请，仅 admin 可操作。"""
    await invite_service.reject_join_request(
        db, redis, team_id, request_id, user["id"]
    )
    return ApiResponse(message="已拒绝")
