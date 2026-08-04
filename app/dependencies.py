"""FastAPI 依赖注入：数据库会话、当前用户等。"""

from typing import Annotated, Any

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_token import extract_bearer_token
from app.core.database import get_db_session
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.redis import get_redis
from app.core.super_admin import is_super_admin
from app.repositories.team_member_repo import team_member_repo
from app.repositories.user_repo import user_repo

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
RedisClient = Annotated[Redis | None, Depends(get_redis)]

FORBIDDEN_ROLE_MESSAGE = "暂无对应角色权限"


async def _load_token_team_user(request: Request, db: AsyncSession) -> dict[str, Any]:
    """从 Token 当前团队加载用户与角色。"""
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


def current_user(*allowed_roles: str):
    """
    基于 Token 当前团队的成员校验。

    allowed_roles 为空时仅校验登录且为当前团队成员；
    非空时额外要求角色在允许列表中。
    """
    async def dependency(
        request: Request,
        db: DbSession,
    ) -> dict[str, Any]:
        user = await _load_token_team_user(request, db)
        if allowed_roles and user["role"] not in allowed_roles:
            raise ForbiddenError(FORBIDDEN_ROLE_MESSAGE)
        return user

    return dependency


def team_access(*allowed_roles: str):
    """
    基于路径 team_id 的成员校验。

    allowed_roles 为空时仅要求是该团队成员；
    非空时额外要求角色在允许列表中。
    """
    async def dependency(
        team_id: int,
        request: Request,
        db: DbSession,
    ) -> dict[str, Any]:
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            raise UnauthorizedError("未授权")

        membership = await team_member_repo.get_membership(
            db, team_id, int(user_id)
        )
        if not membership:
            raise ForbiddenError("无权访问该团队")

        user = {
            "id": user_id,
            "team_id": str(team_id),
            "role": membership.role.value,
        }
        if allowed_roles and membership.role.value not in allowed_roles:
            raise ForbiddenError(FORBIDDEN_ROLE_MESSAGE)
        return user

    return dependency


# 默认：Token 当前团队成员，不限角色
CurrentUser = Annotated[dict[str, Any], Depends(current_user())]

# Token 当前团队：admin 或 tech_lead
CurrentTeamAdminOrLead = Annotated[
    dict[str, Any],
    Depends(current_user("admin", "tech_lead")),
]

# 路径 team_id：任意团队成员
TeamMemberUser = Annotated[dict[str, Any], Depends(team_access())]

# 路径 team_id：仅 admin
TeamAdminUser = Annotated[dict[str, Any], Depends(team_access("admin"))]


async def require_super_admin(
    request: Request,
    db: DbSession,
) -> dict[str, Any]:
    """校验当前用户为超级管理员。"""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise UnauthorizedError("未授权")

    user = await user_repo.get_by_id(db, int(user_id))
    if not user or not is_super_admin(user.id):
        raise ForbiddenError("仅超级管理员可操作")

    if not user.is_active:
        raise ForbiddenError("账号已禁用")

    return {
        "id": user_id,
        "team_id": getattr(request.state, "team_id", None),
        "is_super_admin": True,
    }


SuperAdminUser = Annotated[dict[str, Any], Depends(require_super_admin)]


async def get_access_token(request: Request) -> str:
    """获取当前请求的 Access Token（优先读中间件注入的 state）。"""
    token = getattr(request.state, "access_token", None)
    if token:
        return token
    return extract_bearer_token(request.headers.get("Authorization"))


AccessToken = Annotated[str, Depends(get_access_token)]
