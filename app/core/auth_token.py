"""Access Token 提取与解析（中间件与依赖注入共用）。"""

import jwt

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token


def extract_bearer_token(authorization: str | None) -> str:
    """从 Authorization 头提取 Bearer Token。

    Raises:
        UnauthorizedError: 缺少头或格式不正确。
    """
    if not authorization:
        raise UnauthorizedError("缺少 Authorization 头")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Authorization 格式应为 Bearer <token>")

    return token.strip()


def parse_access_token(token: str) -> dict:
    """解码并校验 Access Token payload。

    Returns:
        含 sub / jti / team_id / role 的 payload。

    Raises:
        UnauthorizedError: Token 无效或已过期。
    """
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Access Token 已过期") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Access Token 无效") from None

    if payload.get("type") and payload.get("type") != "access":
        raise UnauthorizedError("Access Token 无效")

    user_id = payload.get("sub")
    jti = payload.get("jti")
    team_id = payload.get("team_id")
    role = payload.get("role")
    if not user_id or not jti or not team_id or not role:
        raise UnauthorizedError("Access Token 无效")

    return payload
