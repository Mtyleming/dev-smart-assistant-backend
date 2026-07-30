"""应用配置：从环境变量读取，默认值适合本地开发。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置项，修改 .env 即可生效，无需改代码。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "开发智能助手"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # 数据库异步连接 URL（使用 aiomysql 驱动）
    database_url: str = "mysql+aiomysql://root:admin@127.0.0.1:3306/dev_assistant"
    # Redis 异步连接 URL
    redis_url: str = "redis://127.0.0.1:6379/0"
    # JWT 签名密钥，生产环境必须通过环境变量注入
    jwt_secret: str = "change-me-in-production"
    # Access Token 有效期（秒）
    access_token_expire: int = 7200
    # Refresh Token 有效期（秒）
    refresh_token_expire: int = 604800
    # 登录会话 Redis TTL（秒），滑动过期
    login_session_ttl: int = 1800
    # 百炼平台 API Key
    bailian_api_key: str = ""
    # 应用版本号
    app_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例，避免重复解析环境变量。"""
    return Settings()


# 模块级单例，供 main / redis 等直接 import settings 使用
settings = get_settings()
