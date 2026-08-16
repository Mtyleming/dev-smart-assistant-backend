"""文档生成与模板管理的请求/响应模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.base_models import DocumentTemplateType

DocExportFormat = Literal["markdown", "html", "pdf"]


class DocGenerateRequest(BaseModel):
    """生成文档。"""

    doc_type: DocumentTemplateType = Field(
        ..., description="文档类型：api_doc / module_doc / changelog / getting_started / custom"
    )
    input_content: str = Field(..., min_length=1, description="代码片段或自然语言描述")
    is_code: bool = Field(default=False, description="输入是否为代码片段")
    knowledge_base_id: int | None = Field(
        default=None, ge=1, description="可选，仅从指定知识库检索风格参考"
    )
    template_id: int | None = Field(
        default=None,
        ge=1,
        description="可选。指定使用的模板 ID（本团队自定义或系统内置）；不传则按文档类型自动选择",
    )


class DocGenerateData(BaseModel):
    """生成成功返回 Markdown 正文。"""

    content: str = Field(..., description="Markdown 文档（含 AI 声明头）")
    doc_type: str
    template_source: str = Field(
        ..., description="模板来源：custom / builtin_db / builtin_code"
    )
    style_used: bool = Field(..., description="是否注入了知识库风格参考")


class DocExportRequest(BaseModel):
    """导出文档。"""

    content: str = Field(..., min_length=1, description="Markdown 正文")
    format: DocExportFormat = Field(..., description="导出格式：html / pdf / markdown")
    doc_type: str = Field(default="document", description="用于导出文件名")


class TemplateCreateRequest(BaseModel):
    """创建自定义文档模板。"""

    name: str = Field(..., min_length=1, max_length=200, description="模板名称")
    type: DocumentTemplateType = Field(..., description="模板类型")
    content: str = Field(..., min_length=1, description="模板内容（Markdown，可含占位符）")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("模板名称不能为空")
        return text


class TemplateUpdateRequest(BaseModel):
    """更新自定义文档模板：至少提供一个字段。"""

    name: str | None = Field(default=None, min_length=1, max_length=200, description="新名称")
    type: DocumentTemplateType | None = Field(default=None, description="新类型")
    content: str | None = Field(default=None, min_length=1, description="新内容")

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "TemplateUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("至少需要提供 name、type 或 content 之一")
        if "name" in self.model_fields_set and self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("模板名称不能为空")
        return self


class TemplateItem(BaseModel):
    """模板列表/详情项。"""

    id: int
    name: str
    type: str
    content: str
    team_id: int | None
    is_builtin: bool
    version: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class TemplateCreateData(BaseModel):
    """创建成功返回标识。"""

    id: int
    version: int
