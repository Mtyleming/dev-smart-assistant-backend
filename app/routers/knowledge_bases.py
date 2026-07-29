"""知识库模块路由：/api/v1/knowledge-bases。"""

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.services.knowledge_service import knowledge_service

router = APIRouter()


@router.get("", response_model=ApiResponse[list], summary="知识库列表")
async def list_knowledge_bases(
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[list]:
    items = await knowledge_service.list_knowledge_bases(db, user)
    return ApiResponse(data=items)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def knowledge_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="knowledge-bases", detail="知识库管理路由已就绪")
    )
