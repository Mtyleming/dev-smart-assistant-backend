"""消息管理路由：/api/v1/messages。"""

from fastapi import APIRouter

from app.core.config import settings
from app.dependencies import CurrentUser, DbSession, RedisClient
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.message import MessageListData, MessageListRequest, MessageRemoveRequest, ChatRequest, ChatResponseData
from app.services.message_service import message_service
from app.services.chat_service import chat_service

router = APIRouter(
    prefix=settings.api_v1_prefix + "/messages",
    tags=["消息"],
)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def messages_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(data=ModuleStatus(module="messages", detail="消息管理路由已就绪"))


@router.post(
    "/getMessageList",
    response_model=ApiResponse[MessageListData],
    summary="历史消息列表",
)
async def get_message_list(
    body: MessageListRequest,
    db: DbSession,
    user: CurrentUser,
    redis: RedisClient,
) -> ApiResponse[MessageListData]:
    """分页获取指定对话的历史消息。"""
    data = await message_service.get_message_list(
        db, user["id"], user["team_id"], body, redis
    )
    return ApiResponse(data=data)


@router.post(
    "/remove",
    response_model=ApiResponse[None],
    summary="删除消息",
)
async def remove_message(
    body: MessageRemoveRequest,
    db: DbSession,
    user: CurrentUser,
    redis: RedisClient,
) -> ApiResponse[None]:
    """逻辑删除单条消息。"""
    await message_service.remove_message(
        db, user["id"], user["team_id"], body, redis
    )
    return ApiResponse(message="消息已删除")


@router.post(
    "/chat",
    response_model=ApiResponse[ChatResponseData],
    summary="发起对话",
)
async def send_chat_message(
    body: ChatRequest,
    db: DbSession,
    user: CurrentUser,
    redis: RedisClient,
) -> ApiResponse[ChatResponseData]:
    """发送用户消息并获取助手回复。"""
    data = await chat_service.send_message(db, user, body, redis)
    return ApiResponse(data=data)
