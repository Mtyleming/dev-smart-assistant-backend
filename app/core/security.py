"""密码加密与 JWT 签发。"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """使用 bcrypt（rounds=12）加密密码。"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(user_id: str, team_id: str, role: str) -> tuple[str, str]:
    """签发 Access Token，返回 (token, jti)。"""
    return _create_access_token(user_id, team_id, role, settings.access_token_expire)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """签发 Refresh Token，返回 (token, jti)。"""
    return _create_refresh_token(user_id, settings.refresh_token_expire)


def decode_refresh_token(token: str) -> dict:
    """解码并校验 Refresh Token 签名与有效期。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def decode_access_token(token: str) -> dict:
    """解码并校验 Access Token 签名与有效期。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def get_token_remaining_seconds(payload: dict) -> int:
    """计算 Token 剩余有效秒数。"""
    exp = payload.get("exp")
    if exp is None:
        return 0
    remaining = int(exp) - int(datetime.now(UTC).timestamp())
    return max(remaining, 0)


def _create_access_token(
    user_id: str, team_id: str, role: str, expire_seconds: int
) -> tuple[str, str]:
    """生成 Access JWT，payload 含 sub / jti / team_id / role。"""
    jti = str(uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "jti": jti,
        "team_id": team_id,
        "role": role,
        "iat": now,
        "type": "access",
        "exp": now + timedelta(seconds=expire_seconds),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, jti


def _create_refresh_token(user_id: str, expire_seconds: int) -> tuple[str, str]:
    """生成 Refresh JWT，payload 仅含 sub / jti。"""
    jti = str(uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "jti": jti,
        "iat": now,
        "type": "refresh",
        "exp": now + timedelta(seconds=expire_seconds),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token, jti
