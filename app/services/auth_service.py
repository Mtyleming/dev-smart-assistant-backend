"""认证相关业务逻辑。"""

import logging

import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError, AppException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_token_remaining_seconds,
    hash_password,
    verify_password,
)
from app.models.base_models import User, UserRole
from app.repositories.cache_repo import cache_repo
from app.repositories.team_repo import team_repo
from app.repositories.user_repo import user_repo
from app.schemas.auth import (
    AuthData,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UserBasicInfo,
)

logger = logging.getLogger(__name__)


class AuthService:
    """注册、登录等认证业务。"""

    async def register(
        self,
        db: AsyncSession,
        redis: Redis | None,
        payload: RegisterRequest,
    ) -> AuthData:
        """用户注册：创建团队与用户，签发双 Token 并写入会话。

        Args:
            db: 数据库会话。
            redis: Redis 客户端，不可用时跳过会话写入。
            payload: 注册请求参数。

        Returns:
            包含双 Token 与用户基本信息的认证数据。

        Raises:
            ConflictError: 用户名或邮箱已存在。
        """
        existing = await user_repo.get_by_email_or_username(
            db, payload.email, payload.username
        )
        if existing:
            raise ConflictError("用户名或邮箱已被注册")

        team = await team_repo.create(db, payload.username)
        user = await user_repo.create(
            db,
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            team_id=team.id,
            role=UserRole.admin,
        )
        await db.commit()
        await db.refresh(user)

        return await self._issue_auth_data(redis, user)

    async def login(
        self,
        db: AsyncSession,
        redis: Redis | None,
        payload: LoginRequest,
    ) -> AuthData:
        """用户登录：校验账号密码，签发双 Token 并写入会话。

        Args:
            db: 数据库会话。
            redis: Redis 客户端，不可用时跳过会话写入。
            payload: 登录请求参数。

        Returns:
            包含双 Token 与用户基本信息的认证数据。

        Raises:
            NotFoundError: 用户不存在。
            UnauthorizedError: 密码错误。
        """
        user = await user_repo.get_by_number(db, payload.number)
        if not user:
            raise NotFoundError("用户不存在")

        if not user.is_active:
            raise AppException(code=40301, message="账号已禁用", status_code=403)

        if not verify_password(payload.password, user.password_hash):
            raise AppException(code=40101, message="邮箱或密码错误", status_code=401)

        return await self._issue_auth_data(redis, user)

    async def refresh(
        self,
        db: AsyncSession,
        redis: Redis | None,
        param: RefreshRequest,
    ) -> AuthData:
        """使用 Refresh Token 续期，签发新的双 Token。

        Args:
            db: 数据库会话。
            redis: Redis 客户端，用于黑名单校验与写入。
            param: 续期请求参数。

        Returns:
            包含新双 Token 与用户基本信息的认证数据。

        Raises:
            UnauthorizedError: Token 无效、已过期、已失效或 Redis 不可用。
        """
        if redis is None:
            raise UnauthorizedError("Token 续期失败，请重新登录")

        try:
            token_payload = decode_refresh_token(param.refresh_token)
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Refresh Token 已过期") from None
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Refresh Token 无效") from None

        # 检查 Token 类型必须为 refresh
        if token_payload.get("type") != "refresh":
            raise UnauthorizedError("无效的 Refresh Token")

        jti = token_payload.get("jti")
        user_id_str = token_payload.get("sub")
        if not jti or not user_id_str:
            raise UnauthorizedError("Refresh Token 无效")

        try:
            if await cache_repo.is_token_blacklisted(redis, jti):
                raise AppException(code=40103, message="Token 已过期", status_code=401)
        except Exception:
            pass  # Redis 降级时跳过黑名单检查


        user = await user_repo.get_by_id(db, int(user_id_str))
        if not user or not user.is_active:
            raise UnauthorizedError("用户不存在或已禁用")

        remaining_ttl = get_token_remaining_seconds(token_payload)
        auth_data = await self._issue_auth_data(redis, user)
        await cache_repo.add_token_to_blacklist(redis, jti, remaining_ttl)
        return auth_data

    async def _issue_auth_data(self, redis: Redis | None, user: User) -> AuthData:
        """签发双 Token、写入 Redis 会话并组装响应。"""
        user_id = str(user.id)
        team_id = str(user.team_id)
        role = user.role.value

        access_token, access_jti = create_access_token(user_id, team_id, role)
        refresh_token, refresh_jti = create_refresh_token(user_id)

        if redis is not None:
            await cache_repo.set_login_session(
                redis,
                user_id,
                {
                    "access_jti": access_jti,
                    "refresh_jti": refresh_jti,
                    "team_id": team_id,
                    "role": role,
                },
                settings.login_session_ttl,
            )
        else:
            logger.warning("Redis 不可用，跳过登录会话写入 user_id=%s", user_id)

        return AuthData(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserBasicInfo(
                id=user.id,
                username=user.username,
                email=user.email,
                team_id=user.team_id,
                role=role,
                is_active=user.is_active,
            ),
        )


auth_service = AuthService()
