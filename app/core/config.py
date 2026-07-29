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

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = (
        "mysql+aiomysql://root:password@127.0.0.1:3306/dev_smart_assistant"
    )
    redis_url: str = "redis://127.0.0.1:6379/0"

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440

    dashscope_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例，避免重复解析环境变量。"""
    return Settings()
