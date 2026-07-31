"""鉴权中间件：校验 Access Token 并注入用户上下文。"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.auth_token import extract_bearer_token, parse_access_token
from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.redis import redis_client
from app.repositories.cache_repo import cache_repo

logger = logging.getLogger(__name__)

# 无需鉴权的精确路径
PUBLIC_EXACT_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    f"{settings.api_v1_prefix}/auth/register",
    f"{settings.api_v1_prefix}/auth/login",
    f"{settings.api_v1_prefix}/auth/refresh",
}


def _is_public_path(path: str) -> bool:
    """判断请求路径是否跳过鉴权。"""
    if path in PUBLIC_EXACT_PATHS:
        return True
    if path.endswith("/status"):
        return True
    return path.startswith("/docs") or path.startswith("/redoc")


def _unauthorized(message: str) -> JSONResponse:
    """将 UnauthorizedError 转为中间件可返回的 JSON 响应。"""
    exc = UnauthorizedError(message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """校验 Bearer Access Token，并将用户上下文写入 request.state。"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or _is_public_path(request.url.path):
            return await call_next(request)

        try:
            token = extract_bearer_token(request.headers.get("Authorization"))
            payload = parse_access_token(token)
        except UnauthorizedError as exc:
            return _unauthorized(exc.message)

        user_id = payload["sub"]
        jti = payload["jti"]
        team_id = payload["team_id"]

        try:
            await redis_client.ping()
        except Exception:
            logger.warning("Redis 不可用，鉴权失败")
            return _unauthorized("登录态校验失败，请重新登录")

        if await cache_repo.is_token_blacklisted(redis_client, jti):
            return _unauthorized("Access Token 已失效")

        session = await cache_repo.get_login_session(redis_client, user_id)
        if not session:
            return _unauthorized("登录态已失效，请重新登录")

        request.state.access_token = token
        request.state.user_id = user_id
        request.state.team_id = team_id

        await cache_repo.refresh_login_session_ttl(
            redis_client, user_id, settings.login_session_ttl
        )

        return await call_next(request)
