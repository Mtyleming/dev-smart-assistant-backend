"""对话相关请求与响应模型。"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.base_models import ConversationMode


class ConversationListScope(str, Enum):
    """对话列表查询范围。"""

    mine = "mine"
    team = "team"


class ConversationCreateRequest(BaseModel):
    """创建对话请求体。"""

    mode: ConversationMode = Field(..., description="对话模式：qa / code / doc")


class ConversationBriefData(BaseModel):
    """创建对话成功后的简要信息。"""

    id: int
    title: str
    mode: str


class ConversationListItem(BaseModel):
    """对话列表项。"""

    id: int
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime
    user_id: int | None = Field(default=None, description="创建人 ID，scope=team 时返回")
    username: str | None = Field(default=None, description="创建人用户名，scope=team 时返回")


class ConversationListData(BaseModel):
    """分页对话列表。"""

    items: list[ConversationListItem]
    total: int
    page: int


class ConversationDetailData(BaseModel):
    """对话详情。"""

    id: int
    title: str
    mode: str
    created_at: datetime
    updated_at: datetime


class ConversationUpdateTitleRequest(BaseModel):
    """修改对话标题请求体。"""

    title: str = Field(..., min_length=1, max_length=200, description="新标题")
