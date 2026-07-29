"""文档生成路由：/api/v1/doc-generator。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse, ModuleStatus
from app.services.doc_generator_service import doc_generator_service

router = APIRouter()


class GenerateDocRequest(BaseModel):
    """文档生成请求体。"""

    title: str = Field(..., min_length=1, description="文档标题")
    outline: list[str] | None = Field(default=None, description="大纲条目，可选")


@router.post("/generate", response_model=ApiResponse[dict], summary="生成文档")
async def generate_doc(request: GenerateDocRequest) -> ApiResponse[dict]:
    result = await doc_generator_service.generate(request.title, request.outline)
    return ApiResponse(data=result)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def doc_generator_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="doc-generator", detail="文档生成路由已就绪")
    )
