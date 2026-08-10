"""消息相关请求与响应模型。"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageListRequest(BaseModel):
    """历史消息分页查询请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: int = Field(..., alias="conversationId", description="对话 ID")
    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(
        default=20, ge=1, le=100, alias="pageSize", description="每页条数"
    )


class MessageRemoveRequest(BaseModel):
    """删除消息请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    message_id: int = Field(..., alias="messageId", description="消息 ID")
    conversation_id: int = Field(..., alias="conversationId", description="对话 ID")


class MessageListItem(BaseModel):
    """消息列表项。"""

    id: int
    role: str
    content: str
    content_type: str = "text"
    sources: list[dict[str, Any]] | None = None
    created_at: datetime


class MessageListData(BaseModel):
    """分页消息列表。"""

    items: list[MessageListItem]
    total: int
    page: int


class MessageContentTypeEnum(str, Enum):
    """消息内容类型。"""

    text = "text"
    code = "code"


class ChatRequest(BaseModel):
    """发起对话请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(..., min_length=1, description="用户消息内容")
    content_type: MessageContentTypeEnum = Field(
        default=MessageContentTypeEnum.text,
        alias="content_type",
        description="内容类型：text / code",
    )
    conversation_id: int | None = Field(
        default=None,
        alias="conversation_id",
        description="对话 ID，首次发起可不传",
    )
    knowledge_base_id: int | None = Field(
        default=None,
        alias="knowledge_base_id",
        ge=1,
        description="可选知识库 ID；不传则检索当前团队全部知识库",
    )


class ChatMessageItem(BaseModel):
    """对话消息返回项。"""

    id: int
    role: str
    content: str
    content_type: str
    sources: list[dict[str, Any]] | None = None
    created_at: datetime


class ChatResponseData(BaseModel):
    """发起对话成功响应数据。"""

    user_msg: ChatMessageItem
    assistant_msg: ChatMessageItem
