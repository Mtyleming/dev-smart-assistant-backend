"""FastAPI 依赖注入：数据库会话、当前用户等。"""

from typing import Annotated, Any

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_token import extract_bearer_token
from app.core.database import get_db_session
from app.core.exceptions import UnauthorizedError
from app.core.redis import get_redis

# 类型别名：路由里直接写 DbSession / CurrentUser 更清晰
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[Redis | None, Depends(get_redis)]


async def get_current_user(request: Request) -> dict[str, Any]:
    """从 request.state 读取鉴权中间件注入的当前用户上下文。"""
    user_id = getattr(request.state, "user_id", None)
    team_id = getattr(request.state, "team_id", None)
    role = getattr(request.state, "role", None)

    if not user_id or not team_id or not role:
        raise UnauthorizedError("未授权")

    return {
        "id": user_id,
        "team_id": team_id,
        "role": role,
    }


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def get_access_token(request: Request) -> str:
    """获取当前请求的 Access Token（优先读中间件注入的 state）。"""
    token = getattr(request.state, "access_token", None)
    if token:
        return token
    return extract_bearer_token(request.headers.get("Authorization"))


AccessToken = Annotated[str, Depends(get_access_token)]
