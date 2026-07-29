"""用户模块路由：/api/v1/users。"""

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.services.user_service import user_service

router = APIRouter()


@router.get("/me", response_model=ApiResponse[dict], summary="当前用户资料")
async def get_me(db: DbSession, user: CurrentUser) -> ApiResponse[dict]:
    """需要 Authorization: Bearer <token>。"""
    profile = await user_service.get_profile(db, user)
    return ApiResponse(data=profile)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def users_status() -> ApiResponse[ModuleStatus]:
    """无需登录，用于确认路由已挂载。"""
    return ApiResponse(
        data=ModuleStatus(module="users", detail="用户与团队管理路由已就绪")
    )
