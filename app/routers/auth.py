from fastapi import APIRouter

from app.core.config import settings
from app.dependencies import AccessToken, CurrentUser, DbSession, RedisClient
from app.schemas.auth import AuthData, LoginRequest, MeData, RefreshRequest, RegisterRequest
from app.schemas.common import ApiResponse
from app.services.auth_service import auth_service

router = APIRouter(prefix=settings.api_v1_prefix + "/auth", tags=["权限相关"])


@router.get(
    "/me",
    response_model=ApiResponse[MeData],
    summary="获取当前用户信息",
)
async def get_me(user: CurrentUser, db: DbSession) -> ApiResponse[MeData]:
    """从 Token 解析 user_id 并返回用户基本信息。"""
    data = await auth_service.get_me(db, user["id"])
    return ApiResponse(data=data)


@router.post(
    "/register",
    response_model=ApiResponse[AuthData],
    summary="用户注册",
    status_code=201,
)
async def register(
        body: RegisterRequest,
        db: DbSession,
        redis: RedisClient,
) -> ApiResponse[AuthData]:
    """注册新用户，自动创建个人团队并返回双 Token。"""
    data = await auth_service.register(db, redis, body)
    return ApiResponse(data=data)


@router.post(
    "/login",
    response_model=ApiResponse[AuthData],
    summary="用户登录",
)
async def login(
        body: LoginRequest,
        db: DbSession,
        redis: RedisClient,
) -> ApiResponse[AuthData]:
    """使用用户名或邮箱登录，返回双 Token 及用户基本信息。"""
    data = await auth_service.login(db, redis, body)
    return ApiResponse(data=data)


@router.post(
    "/refresh",
    response_model=ApiResponse[AuthData],
    summary="Token 续期",
)
async def refresh_token(
        body: RefreshRequest,
        db: DbSession,
        redis: RedisClient,
) -> ApiResponse[AuthData]:
    """使用 Refresh Token 换取新的双 Token。"""
    data = await auth_service.refresh(db, redis, body)
    return ApiResponse(data=data)


@router.post(
    "/logout",
    response_model=ApiResponse,
    summary="用户登出",
)
async def logout(
        user: CurrentUser,
        access_token: AccessToken,
        redis: RedisClient,
) -> ApiResponse:
    """登出当前用户，作废 Access Token 并清除登录会话。"""
    await auth_service.logout(redis, user["id"], access_token)
    return ApiResponse(message="登出成功")
