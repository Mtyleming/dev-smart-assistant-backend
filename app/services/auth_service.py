"""认证相关业务逻辑。"""

import logging

import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_token import parse_access_token
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
from app.models.base_models import TeamMemberRole, User
from app.repositories.cache_repo import cache_repo
from app.repositories.team_member_repo import team_member_repo
from app.repositories.team_repo import team_repo
from app.repositories.user_repo import user_repo
from app.schemas.auth import (
    AuthData,
    LoginRequest,
    MeData,
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
        """用户注册：创建团队、用户及 team_members 关系，签发双 Token。"""
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
        )
        await team_member_repo.create(
            db,
            team_id=team.id,
            user_id=user.id,
            role=TeamMemberRole.admin,
        )
        await db.commit()
        await db.refresh(user)

        return await self._issue_auth_data(db, redis, user, team.id)

    async def login(
        self,
        db: AsyncSession,
        redis: Redis | None,
        payload: LoginRequest,
    ) -> AuthData:
        """用户登录：校验账号密码，签发双 Token 并写入会话。"""
        user = await user_repo.get_by_number(db, payload.number)
        if not user:
            raise NotFoundError("用户不存在")

        if not user.is_active:
            raise AppException(code=40301, message="账号已禁用", status_code=403)

        if not verify_password(payload.password, user.password_hash):
            raise AppException(code=40101, message="邮箱或密码错误", status_code=401)

        membership = await team_member_repo.get_default_membership(db, user.id)
        if not membership:
            raise AppException(code=40302, message="用户未加入任何团队", status_code=403)

        return await self._issue_auth_data(db, redis, user, membership.team_id)

    async def refresh(
        self,
        db: AsyncSession,
        redis: Redis | None,
        param: RefreshRequest,
    ) -> AuthData:
        """使用 Refresh Token 续期，签发新的双 Token。"""
        if redis is None:
            raise UnauthorizedError("Token 续期失败，请重新登录")

        try:
            token_payload = decode_refresh_token(param.refresh_token)
        except jwt.ExpiredSignatureError:
            raise UnauthorizedError("Refresh Token 已过期") from None
        except jwt.InvalidTokenError:
            raise UnauthorizedError("Refresh Token 无效") from None

        if token_payload.get("type") != "refresh":
            raise UnauthorizedError("无效的 Refresh Token")

        jti = token_payload.get("jti")
        user_id_str = token_payload.get("sub")
        if not jti or not user_id_str:
            raise UnauthorizedError("Refresh Token 无效")

        try:
            if await cache_repo.is_token_blacklisted(redis, jti):
                raise AppException(code=40103, message="Token 已过期", status_code=401)
        except AppException:
            raise
        except Exception:
            pass

        user = await user_repo.get_by_id(db, int(user_id_str))
        if not user or not user.is_active:
            raise UnauthorizedError("用户不存在或已禁用")

        membership = await team_member_repo.get_default_membership(db, user.id)
        if not membership:
            raise AppException(code=40302, message="用户未加入任何团队", status_code=403)

        remaining_ttl = get_token_remaining_seconds(token_payload)
        auth_data = await self._issue_auth_data(db, redis, user, membership.team_id)
        await cache_repo.add_token_to_blacklist(redis, jti, remaining_ttl)
        return auth_data

    async def logout(
        self,
        redis: Redis | None,
        user_id: str,
        access_token: str,
    ) -> None:
        """用户登出：将 Access Token 加入黑名单并清除登录会话。"""
        if redis is None:
            raise UnauthorizedError("登出失败，请稍后重试")

        payload = parse_access_token(access_token)
        jti = payload["jti"]
        remaining_ttl = get_token_remaining_seconds(payload)
        await cache_repo.add_token_to_blacklist(redis, jti, remaining_ttl)
        await cache_repo.delete_login_session(redis, user_id)

    async def get_me(self, db: AsyncSession, user_id: str, team_id: str) -> MeData:
        """根据 user_id + team_id 查用户信息与团队内角色。"""
        user = await user_repo.get_by_id(db, int(user_id))
        if not user:
            raise NotFoundError("用户不存在")

        membership = await team_member_repo.get_membership(
            db, int(team_id), int(user_id)
        )
        if not membership:
            raise UnauthorizedError("无权访问当前团队")

        return MeData(
            id=user.id,
            username=user.username,
            email=user.email,
            role=membership.role.value,
            team_id=int(team_id),
        )

    async def _issue_auth_data(
        self,
        db: AsyncSession,
        redis: Redis | None,
        user: User,
        team_id: int,
    ) -> AuthData:
        """签发双 Token、写入 Redis 会话并组装响应。"""
        membership = await team_member_repo.get_membership(db, team_id, user.id)
        if not membership:
            raise AppException(code=40302, message="用户未加入该团队", status_code=403)

        role = membership.role.value
        user_id = str(user.id)
        team_id_str = str(team_id)

        access_token, access_jti = create_access_token(user_id, team_id_str)
        refresh_token, refresh_jti = create_refresh_token(user_id)

        if redis is not None:
            await cache_repo.set_login_session(
                redis,
                user_id,
                {
                    "access_jti": access_jti,
                    "refresh_jti": refresh_jti,
                    "team_id": team_id_str,
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
                team_id=team_id,
                role=role,
                is_active=user.is_active,
            ),
        )


auth_service = AuthService()