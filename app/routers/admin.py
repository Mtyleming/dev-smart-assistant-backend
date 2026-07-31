"""超级管理员路由：/api/v1/admin。"""

from fastapi import APIRouter

from app.core.config import settings
from app.dependencies import DbSession, RedisClient, SuperAdminUser
from app.schemas.admin import AdminOrganizationTree, UpdateUserStatusRequest
from app.schemas.common import ApiResponse, ModuleStatus
from app.services.admin_service import admin_service

router = APIRouter(prefix=settings.api_v1_prefix + "/admin", tags=["超级管理员"])


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def admin_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="admin", detail="超级管理员路由已就绪")
    )


@router.get(
    "/organization",
    response_model=ApiResponse[AdminOrganizationTree],
    summary="获取组织树",
)
async def get_organization_tree(
    db: DbSession,
    _user: SuperAdminUser,
) -> ApiResponse[AdminOrganizationTree]:
    """获取系统下所有团队与用户，按团队分组，成员按 admin → tech_lead → developer 排序。"""
    data = await admin_service.get_organization_tree(db)
    return ApiResponse(data=data)


@router.put(
    "/users/{user_id}/status",
    response_model=ApiResponse[None],
    summary="启用/停用用户",
)
async def update_user_status(
    user_id: int,
    body: UpdateUserStatusRequest,
    db: DbSession,
    redis: RedisClient,
    user: SuperAdminUser,
) -> ApiResponse[None]:
    """启用或停用用户；停用后该用户登录态立即失效。"""
    await admin_service.update_user_status(
        db, redis, user["id"], user_id, body
    )
    message = "用户已启用" if body.is_active else "用户已停用"
    return ApiResponse(message=message)
