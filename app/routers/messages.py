"""消息管理路由：/api/v1/messages。"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.event_stream import event_stream, format_sse_event
from app.core.exceptions import AppException
from app.dependencies import CurrentUser, DbSession, RedisClient
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.message import (
    ChatRequest,
    MessageListData,
    MessageListRequest,
    MessageRemoveRequest,
)
from app.services.chat_service import chat_service
from app.services.message_service import message_service

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
    summary="发起对话（SSE 流式）",
    response_class=StreamingResponse,
)
async def send_chat_message(
    body: ChatRequest,
    user: CurrentUser,
    redis: RedisClient,
) -> StreamingResponse:
    """发送用户消息并以 SSE 流式返回助手回复。"""

    async def stream_events():
        try:
            async with async_session_factory() as db:
                events = chat_service.send_message_stream(db, user, body, redis)
                async for sse_chunk in event_stream(events):
                    yield sse_chunk
        except AppException as exc:
            yield format_sse_event(
                "error",
                {"code": exc.code, "message": exc.message},
            )
        except Exception:
            yield format_sse_event(
                "error",
                {"code": 50000, "message": "服务内部错误"},
            )

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
