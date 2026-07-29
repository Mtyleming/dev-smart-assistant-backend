from redis.asyncio import Redis, ConnectionPool
from app.core.config import settings

# 异步 Redis 连接池，最大连接数 50
pool = ConnectionPool.from_url(settings.redis_url, max_connections=50, decode_responses=True)
redis_client = Redis(connection_pool=pool)

async def get_redis():
    """FastAPI 依赖注入：获取 Redis 客户端（支持降级）"""
    try:
        await redis_client.ping()
        return redis_client
    except Exception:
        # Redis 不可用时返回 None，业务层需处理降级逻辑
        return None