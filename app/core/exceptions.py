"""业务异常：服务层抛出，路由层统一转成 HTTP 响应。"""


class AppError(Exception):
    """应用业务异常基类。"""

    def __init__(self, message: str, code: str = "APP_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class UnauthorizedError(AppError):
    """未登录或 Token 无效。"""

    def __init__(self, message: str = "未授权") -> None:
        super().__init__(message=message, code="UNAUTHORIZED")


class NotFoundError(AppError):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message=message, code="NOT_FOUND")
