"""智能问答路由：/api/v1/chat。"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.dependencies import CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.services.chat_service import chat_service

router = APIRouter()


class AskRequest(BaseModel):
    """问答请求体。"""

    question: str = Field(..., min_length=1, description="用户问题")
    conversation_id: str = Field(..., min_length=1, description="对话 ID")


@router.post("/ask", response_model=ApiResponse[dict], summary="发起问答")
async def ask_question(
    request: AskRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[dict]:
    """路由层只调服务层，不直接接触 AI。"""
    result = await chat_service.ask(
        db, user, request.question, request.conversation_id
    )
    return ApiResponse(data=result)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def chat_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="chat", detail="智能问答引擎路由已就绪")
    )
