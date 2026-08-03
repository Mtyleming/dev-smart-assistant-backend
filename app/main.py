"""FastAPI 应用入口：创建应用并挂载路由。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import AppException, app_exception_handler, global_exception_handler
from app.core.redis import redis_client
from app.middleware.auth_middleware import AuthMiddleware
import app.models  # noqa: F401  注册 ORM 模型到 Base.metadata
from app.routers import (
    admin,
    auth,
    conversations,
    health,
    teams,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期：启动时尝试建表，退出时释放资源。"""
    logging.basicConfig(
        level=logging.DEBUG if settings.app_debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表检查/创建完成")
    except Exception as exc:
        # 本地还没起 MySQL 时也能先启动服务看文档
        logger.warning("数据库暂不可用，跳过建表：%s", exc)

    yield

    await engine.dispose()
    await redis_client.close()
    logger.info("服务资源已释放")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# 健康检查
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(conversations.router)
app.include_router(admin.router)

