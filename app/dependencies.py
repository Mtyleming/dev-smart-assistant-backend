"""FastAPI 依赖注入：数据库会话、当前用户等。"""

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.exceptions import UnauthorizedError

# 类型别名：路由里直接写 DbSession / CurrentUser 更清晰
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """
    从 Authorization 头解析当前用户（开发阶段占位）。

    正式环境应校验 JWT / Session；当前仅保证依赖注入链路可用。
    约定：Authorization: Bearer demo-token
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization 头",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 格式应为 Bearer <token>",
        )

    # 开发占位：任意非空 token 都视为演示用户
    if token.strip() == "":
        raise UnauthorizedError("Token 无效")

    return {
        "id": "demo-user-id",
        "username": "demo",
        "display_name": "演示用户",
        "team_id": "demo-team-id",
        "accessible_kb_ids": [],
    }


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
