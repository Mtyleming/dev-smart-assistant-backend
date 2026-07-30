"""Redis 缓存封装。"""

from redis.asyncio import Redis


class CacheRepository:
    """缓存读写，不包含业务判断。"""

    async def set_login_session(
        self,
        redis: Redis,
        user_id: str,
        session_data: dict[str, str],
        ttl_seconds: int,
    ) -> None:
        """写入登录会话 Hash，并设置滑动过期 TTL。"""
        key = f"session:login:{user_id}"
        await redis.hset(key, mapping=session_data)
        await redis.expire(key, ttl_seconds)

    async def is_token_blacklisted(self, redis: Redis, jti: str) -> bool:
        """检查 Refresh Token 的 jti 是否在黑名单中。"""
        return bool(await redis.exists(f"session:blacklist:{jti}"))

    async def add_token_to_blacklist(
        self, redis: Redis, jti: str, ttl_seconds: int
    ) -> None:
        """将 Refresh Token 的 jti 写入黑名单。"""
        if ttl_seconds > 0:
            await redis.setex(f"session:blacklist:{jti}", ttl_seconds, "1")


cache_repo = CacheRepository()
