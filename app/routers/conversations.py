"""对话管理路由：/api/v1/conversations。"""

from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.repositories.conversation_repo import conversation_repo
from app.schemas.common import ApiResponse, ModuleStatus

router = APIRouter()


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def conversations_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="conversations", detail="对话管理路由已就绪")
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=ApiResponse[list],
    summary="对话消息列表",
)
async def list_messages(
    conversation_id: str,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[list]:
    messages = await conversation_repo.list_messages(
        db, conversation_id, user["team_id"]
    )
    return ApiResponse(data=messages)
