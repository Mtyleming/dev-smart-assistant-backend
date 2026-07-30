"""用户模块路由：/api/v1/users。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse, ModuleStatus

router = APIRouter()



@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def users_status() -> ApiResponse[ModuleStatus]:
    """无需登录，用于确认路由已挂载。"""
    return ApiResponse(
        data=ModuleStatus(module="users", detail="用户与团队管理路由已就绪")
    )
