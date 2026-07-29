"""异步数据库引擎与会话工厂（SQLAlchemy 2.0）。"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# 异步引擎：连接池大小与选型文档保持一致
engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    echo=settings.app_debug,
)

# 会话工厂：每个请求独立会话，提交后不过期对象
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：按请求提供数据库会话，结束时自动关闭。"""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
