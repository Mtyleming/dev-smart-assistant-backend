"""Redis 缓存封装（骨架占位）。"""


class CacheRepository:
    """缓存读写，不包含业务判断。"""

    async def get(self, key: str) -> str | None:
        """读取缓存。"""
        _ = key
        return None

    async def set(self, key: str, value: str, ttl_seconds: int = 3600) -> None:
        """写入缓存。"""
        _ = (key, value, ttl_seconds)
        return None


cache_repo = CacheRepository()
