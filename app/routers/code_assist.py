"""代码辅助路由：/api/v1/code-assist。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse, ModuleStatus
from app.services.code_assist_service import code_assist_service

router = APIRouter()


class AssistRequest(BaseModel):
    """代码辅助请求体。"""

    question: str = Field(..., min_length=1, description="代码相关问题")
    language: str | None = Field(default=None, description="编程语言，可选")


@router.post("/assist", response_model=ApiResponse[dict], summary="代码辅助")
async def assist(request: AssistRequest) -> ApiResponse[dict]:
    result = await code_assist_service.assist(request.question, request.language)
    return ApiResponse(data=result)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def code_assist_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="code-assist", detail="代码辅助路由已就绪")
    )
