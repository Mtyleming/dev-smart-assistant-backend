"""通用响应结构。"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.config import get_settings

T = TypeVar("T")
settings = get_settings()


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应包装，前端按 code/message/data 解析即可。"""

    code: int = Field(default=0, description="业务状态码，0 表示成功")
    message: str = Field(default="ok", description="提示信息")
    data: T | None = Field(default=None, description="业务数据")


class HealthData(BaseModel):
    """健康检查返回数据。"""

    status: str = "ok"
    service: str = settings.app_name
    version: str = settings.app_version


class ModuleStatus(BaseModel):
    """模块占位状态，方便前端联调时确认路由已挂载。"""

    module: str
    status: str = "ready"
    detail: str | dict[str, Any] | None = None
