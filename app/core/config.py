"""应用配置：从环境变量读取，默认值适合本地开发。"""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
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
    # 百炼 / DashScope API Key（.env 中使用 DASHSCOPE_API_KEY）
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DASHSCOPE_API_KEY", "BAILIAN_API_KEY"),
    )
    # DashScope 兼容模式地址（国内站默认；国际站 Key 需改为 dashscope-intl 域名）
    llm_api_base: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("DASHSCOPE_API_BASE", "LLM_API_BASE"),
    )
    # 对话模型名称（如 qwen-plus、qwen-max、qwen-turbo）
    llm_model: str = Field(
        default="qwen3.7-plus",
        validation_alias=AliasChoices("LLM_MODEL", "DASHSCOPE_MODEL"),
    )
    # 文本向量模型（百炼 text-embedding-v4）
    embedding_model: str = Field(
        default="text-embedding-v4",
        validation_alias=AliasChoices("EMBEDDING_MODEL"),
    )
    # 向量维度（与 Milvus FLOAT_VECTOR dim 一致；v4 默认 1024）
    embedding_dimensions: int = Field(
        default=1024,
        validation_alias=AliasChoices("EMBEDDING_DIMENSIONS"),
    )
    # 单次 Embedding 请求最大文本条数（百炼上限 10）
    embedding_batch_size: int = Field(
        default=10,
        validation_alias=AliasChoices("EMBEDDING_BATCH_SIZE"),
    )

    @field_validator("llm_api_key", mode="before")
    @classmethod
    def strip_llm_api_key(cls, value: object) -> object:
        """去除 API Key 首尾空白，避免 .env 误输入导致 401。"""
        if isinstance(value, str):
            return value.strip()
        return value
    # 应用版本号
    app_version: str = "0.1.0"
    # 超级管理员用户 ID（写死，不修改 users 表结构）
    super_admin_user_id: int = 15
    # Milvus 连接地址（本地默认）
    milvus_uri: str = Field(
        default="http://127.0.0.1:19530",
        validation_alias=AliasChoices("MILVUS_URI"),
    )
    # 文档切块向量 Collection 名
    milvus_collection: str = Field(
        default="document_chunks",
        validation_alias=AliasChoices("MILVUS_COLLECTION"),
    )
    # 知识库文档本地存储目录
    upload_dir: str = Field(
        default="uploads",
        validation_alias=AliasChoices("UPLOAD_DIR"),
    )
    # 单文件最大上传体积（字节），默认 20MB
    upload_max_bytes: int = Field(
        default=20 * 1024 * 1024,
        validation_alias=AliasChoices("UPLOAD_MAX_BYTES"),
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置实例，避免重复解析环境变量。"""
    return Settings()


# 模块级单例，供 main / redis 等直接 import settings 使用
settings = get_settings()
