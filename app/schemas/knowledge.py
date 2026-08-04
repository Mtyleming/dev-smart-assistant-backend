"""知识库请求与响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeCreateRequest(BaseModel):
    """创建知识库。"""

    name: str = Field(..., min_length=1, max_length=200, description="知识库名称")
    description: str | None = Field(default=None, description="知识库描述")


class KnowledgePageRequest(BaseModel):
    """分页查询知识库。"""

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(
        default=20, ge=1, le=100, alias="pageSize", description="每页条数"
    )
    keyword: str | None = Field(default=None, description="按名称模糊搜索")


class KnowledgeIdRequest(BaseModel):
    """按 ID 操作（详情/删除）。"""

    id: int = Field(..., ge=1, description="知识库 ID")


class KnowledgeUpdateRequest(BaseModel):
    """修改知识库：至少提供 name 或 description 之一。"""

    id: int = Field(..., ge=1, description="知识库 ID")
    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="新名称"
    )
    description: str | None = Field(
        default=None, description="新描述，传 null 可清空"
    )

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "KnowledgeUpdateRequest":
        # 用 fields_set 区分「未传 description」与「显式传 null」
        provided = self.model_fields_set - {"id"}
        if not provided:
            raise ValueError("至少需要提供 name 或 description 之一")
        if "name" in provided and self.name is None:
            raise ValueError("name 不能为空")
        return self


class KnowledgeItem(BaseModel):
    """知识库详情/列表项。"""

    id: int
    name: str
    description: str | None
    team_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime


class KnowledgeCreateData(BaseModel):
    """创建成功返回标识。"""

    id: int


class KnowledgePageData(BaseModel):
    """分页列表。"""

    items: list[KnowledgeItem]
    total: int
    page: int
