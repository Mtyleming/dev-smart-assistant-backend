"""对话管理路由：/api/v1/conversations。"""

from fastapi import APIRouter, Query

from app.core.config import settings
from app.dependencies import CurrentUser, DbSession
from app.models.base_models import ConversationMode
from app.repositories.message_repo import message_repo
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.conversation import (
    ConversationBriefData,
    ConversationCreateRequest,
    ConversationDetailData,
    ConversationListData,
    ConversationListScope,
    ConversationUpdateTitleRequest,
)
from app.services.conversation_service import conversation_service

router = APIRouter(
    prefix=settings.api_v1_prefix + "/conversations",
    tags=["对话"],
)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def conversations_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="conversations", detail="对话管理路由已就绪")
    )


@router.post(
    "",
    response_model=ApiResponse[ConversationBriefData],
    summary="创建对话",
    status_code=201,
)
async def create_conversation(
    body: ConversationCreateRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[ConversationBriefData]:
    """创建新对话，mode 必须为 qa / code / doc 之一。"""
    data = await conversation_service.create_conversation(
        db, user["id"], user["team_id"], body.mode
    )
    return ApiResponse(data=data)


@router.get(
    "",
    response_model=ApiResponse[ConversationListData],
    summary="获取对话列表",
)
async def list_conversations(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    title: str | None = Query(default=None, description="标题模糊匹配"),
    mode: ConversationMode | None = Query(default=None, description="对话模式筛选"),
    scope: ConversationListScope = Query(
        default=ConversationListScope.mine,
        description="查询范围：mine 仅本人，team 当前团队全部（仅 admin）",
    ),
    username: str | None = Query(
        default=None,
        description="仅 scope=team 时生效，按创建人用户名模糊匹配",
    ),
) -> ApiResponse[ConversationListData]:
    """分页获取对话列表，按修改时间倒序。"""
    data = await conversation_service.list_conversations(
        db,
        user,
        page=page,
        page_size=page_size,
        title=title,
        mode=mode,
        scope=scope,
        username=username,
    )
    return ApiResponse(data=data)


@router.get(
    "/{conversation_id}/messages",
    response_model=ApiResponse[list],
    summary="对话消息列表",
)
async def list_messages(
    conversation_id: int,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[list]:
    messages = await message_repo.list_messages(
        db, conversation_id, int(user["team_id"])
    )
    return ApiResponse(data=messages)


@router.get(
    "/{conversation_id}",
    response_model=ApiResponse[ConversationDetailData],
    summary="获取对话详情",
)
async def get_conversation(
    conversation_id: int,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[ConversationDetailData]:
    """根据 ID 获取单个对话。"""
    data = await conversation_service.get_conversation(
        db, conversation_id, user["id"], user["team_id"]
    )
    return ApiResponse(data=data)


@router.put(
    "/{conversation_id}/title",
    response_model=ApiResponse[None],
    summary="修改对话标题",
)
async def update_conversation_title(
    conversation_id: int,
    body: ConversationUpdateTitleRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[None]:
    """修改对话标题。"""
    await conversation_service.update_title(
        db, conversation_id, user["id"], user["team_id"], body
    )
    return ApiResponse(message="标题已更新")


@router.delete(
    "/{conversation_id}",
    response_model=ApiResponse[None],
    summary="删除对话",
)
async def delete_conversation(
    conversation_id: int,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[None]:
    """逻辑删除对话。"""
    await conversation_service.delete_conversation(
        db, conversation_id, user["id"], user["team_id"]
    )
    return ApiResponse(message="对话已删除")
