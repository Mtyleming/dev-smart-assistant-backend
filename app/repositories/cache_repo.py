"""Redis 缓存封装。"""

from redis.asyncio import Redis

# 邀请码有效期 7 天
INVITE_CODE_TTL_SECONDS = 604800
# 入团审批记录保留 30 天
JOIN_REQUEST_TTL_SECONDS = 30 * 24 * 3600


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
        """检查 Token 的 jti 是否在黑名单中。"""
        return bool(await redis.exists(f"session:blacklist:{jti}"))

    async def get_login_session(self, redis: Redis, user_id: str) -> dict[str, str] | None:
        """获取用户登录会话，不存在时返回 None。"""
        data = await redis.hgetall(f"session:login:{user_id}")
        return data if data else None

    async def refresh_login_session_ttl(
        self, redis: Redis, user_id: str, ttl_seconds: int
    ) -> None:
        """刷新登录会话 TTL（滑动续期）。"""
        await redis.expire(f"session:login:{user_id}", ttl_seconds)

    async def add_token_to_blacklist(
        self, redis: Redis, jti: str, ttl_seconds: int
    ) -> None:
        """将 Token 的 jti 写入黑名单。"""
        if ttl_seconds > 0:
            await redis.setex(f"session:blacklist:{jti}", ttl_seconds, "1")

    async def delete_login_session(self, redis: Redis, user_id: str) -> None:
        """删除用户登录会话。"""
        await redis.delete(f"session:login:{user_id}")

    async def set_invite_code(
        self,
        redis: Redis,
        code: str,
        data: dict[str, str],
        ttl_seconds: int = INVITE_CODE_TTL_SECONDS,
    ) -> None:
        """写入邀请码 Hash 并设置 TTL。"""
        key = f"invite:code:{code}"
        await redis.hset(key, mapping=data)
        await redis.expire(key, ttl_seconds)

    async def get_invite_code(self, redis: Redis, code: str) -> dict[str, str] | None:
        """获取邀请码数据，不存在时返回 None。"""
        data = await redis.hgetall(f"invite:code:{code}")
        return data if data else None

    async def delete_invite_code(self, redis: Redis, code: str) -> None:
        """删除邀请码。"""
        await redis.delete(f"invite:code:{code}")

    async def create_join_request(
        self,
        redis: Redis,
        request_id: str,
        data: dict[str, str],
        ttl_seconds: int = JOIN_REQUEST_TTL_SECONDS,
    ) -> None:
        """写入入团审批 Hash 并设置 TTL。"""
        key = f"join_request:{request_id}"
        await redis.hset(key, mapping=data)
        await redis.expire(key, ttl_seconds)

    async def get_join_request(
        self, redis: Redis, request_id: str
    ) -> dict[str, str] | None:
        """获取入团审批记录，不存在时返回 None。"""
        data = await redis.hgetall(f"join_request:{request_id}")
        return data if data else None

    async def add_team_pending_request(
        self, redis: Redis, team_id: int, request_id: str
    ) -> None:
        """将审批 ID 加入团队待审批集合。"""
        await redis.sadd(f"team:join_pending:{team_id}", request_id)

    async def list_team_pending_request_ids(
        self, redis: Redis, team_id: int
    ) -> list[str]:
        """列出团队所有待审批 ID。"""
        members = await redis.smembers(f"team:join_pending:{team_id}")
        return list(members)

    async def remove_team_pending_request(
        self, redis: Redis, team_id: int, request_id: str
    ) -> None:
        """从团队待审批集合移除审批 ID。"""
        await redis.srem(f"team:join_pending:{team_id}", request_id)

    async def delete_join_request(self, redis: Redis, request_id: str) -> None:
        """删除入团审批记录。"""
        await redis.delete(f"join_request:{request_id}")


cache_repo = CacheRepository()
