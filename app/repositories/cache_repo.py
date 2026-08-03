"""Redis 缓存封装。"""

import json
from datetime import datetime
from typing import Any

from redis.asyncio import Redis

# 邀请码有效期 7 天
INVITE_CODE_TTL_SECONDS = 604800
# 入团审批记录保留 30 天
JOIN_REQUEST_TTL_SECONDS = 30 * 24 * 3600
# 对话消息列表缓存 15 分钟
CONVERSATION_MESSAGES_TTL_SECONDS = 15 * 60
# 对话消息处理分布式锁 30 秒
CONVERSATION_LOCK_TTL_SECONDS = 30
# 上下文超过该条数时触发摘要
CONVERSATION_CONTEXT_SUMMARY_THRESHOLD = 20
# 摘要后保留的最近消息条数
CONVERSATION_CONTEXT_RECENT_KEEP = 10


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

    def _conversation_messages_key(self, conversation_id: int) -> str:
        """对话消息列表缓存 Key。"""
        return f"conv:msg:{conversation_id}"

    def _serialize_message_items(self, messages: list[dict[str, Any]]) -> str:
        """将消息列表序列化为 JSON 字符串。"""
        serialized: list[dict[str, Any]] = []
        for message in messages:
            item = dict(message)
            created_at = item.get("created_at")
            if isinstance(created_at, datetime):
                item["created_at"] = created_at.isoformat()
            serialized.append(item)
        return json.dumps(serialized, ensure_ascii=False)

    async def get_conversation_messages(
        self, redis: Redis, conversation_id: int
    ) -> list[dict[str, Any]] | None:
        """获取对话消息列表缓存，不存在时返回 None。"""
        data = await redis.get(self._conversation_messages_key(conversation_id))
        if data is None:
            return None
        return json.loads(data)

    async def set_conversation_messages(
        self,
        redis: Redis,
        conversation_id: int,
        messages: list[dict[str, Any]],
        ttl_seconds: int = CONVERSATION_MESSAGES_TTL_SECONDS,
    ) -> None:
        """写入对话消息列表缓存并设置 TTL。"""
        key = self._conversation_messages_key(conversation_id)
        await redis.setex(key, ttl_seconds, self._serialize_message_items(messages))

    async def refresh_conversation_messages_ttl(
        self,
        redis: Redis,
        conversation_id: int,
        ttl_seconds: int = CONVERSATION_MESSAGES_TTL_SECONDS,
    ) -> None:
        """刷新对话消息列表缓存 TTL（滑动续期）。"""
        await redis.expire(self._conversation_messages_key(conversation_id), ttl_seconds)

    async def delete_conversation_messages(
        self, redis: Redis, conversation_id: int
    ) -> None:
        """删除对话消息列表缓存。"""
        await redis.delete(self._conversation_messages_key(conversation_id))

    def _conversation_lock_key(self, conversation_id: int) -> str:
        """对话消息处理分布式锁 Key。"""
        return f"conv:lock:{conversation_id}"

    async def acquire_conversation_lock(
        self,
        redis: Redis,
        conversation_id: int,
        ttl_seconds: int = CONVERSATION_LOCK_TTL_SECONDS,
    ) -> bool:
        """尝试获取对话分布式锁（SETNX）。"""
        return bool(
            await redis.set(
                self._conversation_lock_key(conversation_id),
                "1",
                nx=True,
                ex=ttl_seconds,
            )
        )

    async def release_conversation_lock(
        self, redis: Redis, conversation_id: int
    ) -> None:
        """释放对话分布式锁。"""
        await redis.delete(self._conversation_lock_key(conversation_id))

    async def append_conversation_message(
        self,
        redis: Redis,
        conversation_id: int,
        message: dict[str, Any],
        ttl_seconds: int = CONVERSATION_MESSAGES_TTL_SECONDS,
    ) -> list[dict[str, Any]]:
        """向对话消息列表缓存追加一条消息并刷新 TTL。"""
        messages = await self.get_conversation_messages(redis, conversation_id) or []
        messages.append(message)
        await self.set_conversation_messages(
            redis, conversation_id, messages, ttl_seconds
        )
        return messages


cache_repo = CacheRepository()
