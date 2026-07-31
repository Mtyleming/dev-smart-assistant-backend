"""FastAPI 依赖注入：数据库会话、当前用户等。"""

from typing import Annotated, Any

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_token import extract_bearer_token
from app.core.database import get_db_session
from app.core.exceptions import UnauthorizedError
from app.core.redis import get_redis
from app.repositories.team_member_repo import team_member_repo

# 类型别名：路由里直接写 DbSession / CurrentUser 更清晰
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[Redis | None, Depends(get_redis)]


async def get_current_user(request: Request, db: DbSession) -> dict[str, Any]:
    """从 request.state 读取用户上下文，并按 team_members 查询当前团队角色。"""
    user_id = getattr(request.state, "user_id", None)
    team_id = getattr(request.state, "team_id", None)

    if not user_id or not team_id:
        raise UnauthorizedError("未授权")

    membership = await team_member_repo.get_membership(
        db, int(team_id), int(user_id)
    )
    if not membership:
        raise UnauthorizedError("无权访问当前团队")

    return {
        "id": user_id,
        "team_id": team_id,
        "role": membership.role.value,
    }


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def get_access_token(request: Request) -> str:
    """获取当前请求的 Access Token（优先读中间件注入的 state）。"""
    token = getattr(request.state, "access_token", None)
    if token:
        return token
    return extract_bearer_token(request.headers.get("Authorization"))


AccessToken = Annotated[str, Depends(get_access_token)]
