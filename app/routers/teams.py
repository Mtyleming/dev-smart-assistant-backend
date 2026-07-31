"""团队模块路由：/api/v1/teams。"""

from fastapi import APIRouter

from app.core.config import settings
from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.team import (
    TeamBriefData,
    TeamCreateRequest,
    TeamDetailData,
    TeamMemberData,
    TeamUpdateRequest,
)
from app.services.team_service import team_service

router = APIRouter(prefix=settings.api_v1_prefix + "/teams", tags=["团队"])


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def teams_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="teams", detail="团队管理路由已就绪")
    )


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
    "/{team_id}",
    response_model=ApiResponse[TeamDetailData],
    summary="获取团队详情",
)
async def get_team(
    team_id: int,
    db: DbSession,
    user: CurrentUser,
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
    user: CurrentUser,
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
    user: CurrentUser,
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
    user: CurrentUser,
) -> ApiResponse[list[TeamMemberData]]:
    """获取团队成员列表，需为团队成员。"""
    data = await team_service.list_members(db, team_id, user["id"])
    return ApiResponse(data=data)
