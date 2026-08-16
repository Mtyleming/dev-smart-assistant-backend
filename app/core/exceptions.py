"""业务异常：服务层抛出，路由层统一转成 HTTP 响应。"""

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """应用业务异常基类。"""

    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class UnauthorizedError(AppException):
    """未登录或 Token 无效。"""

    def __init__(self, message: str = "未授权"):
        super().__init__(code=40100, message=message, status_code=401)


class NotFoundError(AppException):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=40400, message=message, status_code=404)


class ConflictError(AppException):
    """资源冲突，如用户名或邮箱已存在。"""

    def __init__(self, message: str = "资源冲突"):
        super().__init__(code=40900, message=message, status_code=409)


class ForbiddenError(AppException):
    """无权限执行该操作。"""

    def __init__(self, message: str = "无权限"):
        super().__init__(code=40300, message=message, status_code=403)


class UnsupportedFormatError(AppException):
    """不支持的导出格式。"""

    def __init__(self, message: str = "不支持的导出格式"):
        super().__init__(code=40001, message=message, status_code=400)


async def app_exception_handler(request: Request, exc: AppException):
    """全局业务异常处理器，返回统一 JSON 结构。"""
    _ = request
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


async def global_exception_handler(request: Request, exc: Exception):
    """全局未预期异常处理器，避免泄露内部堆栈。"""
    _ = (request, exc)
    return JSONResponse(
        status_code=500,
        content={"code": 50000, "message": "服务内部错误", "data": None},
    )
