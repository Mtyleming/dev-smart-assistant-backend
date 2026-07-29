"""健康检查：不挂在 /api/v1 下，方便运维探测。"""

from fastapi import APIRouter

from app.core.redis import get_redis
from app.schemas.common import ApiResponse, HealthData

router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=ApiResponse[HealthData], summary="健康检查")
async def health() -> ApiResponse[HealthData]:
    print(await get_redis())
    return ApiResponse(data=HealthData())
