"""FastAPI 应用入口：创建应用并挂载全部 /api/v1 路由。"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError, UnauthorizedError
from app.routers import (
    chat,
    code_assist,
    conversations,
    doc_generator,
    health,
    knowledge_bases,
    teams,
    users,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用启动/关闭钩子：后续可在此初始化连接池等。"""
    logging.basicConfig(
        level=logging.DEBUG if settings.app_debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger.info("服务启动：%s (%s)", settings.app_name, settings.app_env)
    yield
    logger.info("服务关闭")


def create_app() -> FastAPI:
    """工厂方法：创建并配置 FastAPI 实例。"""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="开发智能助手后端 API（FastAPI + SQLAlchemy 异步三层架构）",
        lifespan=lifespan,
    )

    # 开发阶段放开跨域，方便前端本地联调
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(_request: Request, exc: UnauthorizedError):
        return JSONResponse(
            status_code=401,
            content={"code": 401, "message": exc.message, "data": None},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content={"code": 404, "message": exc.message, "data": None},
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        logger.warning("业务异常 [%s]: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=400,
            content={"code": 400, "message": exc.message, "data": None},
        )

    prefix = settings.api_v1_prefix

    app.include_router(health.router)
    app.include_router(users.router, prefix=f"{prefix}/users", tags=["用户与团队管理"])
    app.include_router(teams.router, prefix=f"{prefix}/teams", tags=["用户与团队管理"])
    app.include_router(
        knowledge_bases.router,
        prefix=f"{prefix}/knowledge-bases",
        tags=["知识库管理"],
    )
    app.include_router(
        conversations.router,
        prefix=f"{prefix}/conversations",
        tags=["对话管理"],
    )
    app.include_router(chat.router, prefix=f"{prefix}/chat", tags=["智能问答引擎"])
    app.include_router(
        code_assist.router,
        prefix=f"{prefix}/code-assist",
        tags=["代码辅助"],
    )
    app.include_router(
        doc_generator.router,
        prefix=f"{prefix}/doc-generator",
        tags=["文档生成"],
    )

    return app


app = create_app()
