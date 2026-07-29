"""团队模块路由：/api/v1/teams。"""

from fastapi import APIRouter

from app.schemas.common import ApiResponse, ModuleStatus

router = APIRouter()


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def teams_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="teams", detail="团队管理路由已就绪")
    )
