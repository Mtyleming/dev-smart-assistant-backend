"""文档生成路由：/api/v1/docs。"""

from fastapi import APIRouter
from fastapi.responses import Response

from app.core.config import settings
from app.dependencies import CurrentTeamAdminOrLead, CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.docs import (
    DocExportRequest,
    DocGenerateData,
    DocGenerateRequest,
    TemplateCreateData,
    TemplateCreateRequest,
    TemplateItem,
    TemplateUpdateRequest,
)
from app.services.doc_generator_service import doc_generator_service

router = APIRouter(
    prefix=settings.api_v1_prefix + "/docs",
    tags=["文档生成"],
)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def docs_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="docs", detail="文档生成路由已就绪")
    )


@router.post(
    "/generate",
    response_model=ApiResponse[DocGenerateData],
    summary="生成文档",
)
async def generate_doc(
    body: DocGenerateRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[DocGenerateData]:
    data = await doc_generator_service.generate(db, user, body)
    return ApiResponse(message="生成成功", data=data)


@router.post("/export", summary="导出文档")
async def export_doc(
    body: DocExportRequest,
    user: CurrentUser,
) -> Response:
    _ = user
    raw, media_type, filename = await doc_generator_service.export(body)
    return Response(
        content=raw,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/templates",
    response_model=ApiResponse[list[TemplateItem]],
    summary="获取模板列表",
)
async def list_templates(
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[list[TemplateItem]]:
    data = await doc_generator_service.list_templates(db, user)
    return ApiResponse(data=data)


@router.post(
    "/templates",
    response_model=ApiResponse[TemplateCreateData],
    summary="创建模板",
    status_code=201,
)
async def create_template(
    body: TemplateCreateRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[TemplateCreateData]:
    data = await doc_generator_service.create_template(db, user, body)
    return ApiResponse(message="创建成功", data=data)


@router.put(
    "/templates/{template_id}",
    response_model=ApiResponse[TemplateItem],
    summary="更新模板",
)
async def update_template(
    template_id: int,
    body: TemplateUpdateRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[TemplateItem]:
    data = await doc_generator_service.update_template(db, user, template_id, body)
    return ApiResponse(message="更新成功", data=data)


@router.delete(
    "/templates/{template_id}",
    response_model=ApiResponse[None],
    summary="删除模板",
)
async def delete_template(
    template_id: int,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[None]:
    await doc_generator_service.delete_template(db, user, template_id)
    return ApiResponse(message="删除成功", data=None)
