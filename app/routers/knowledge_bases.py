"""知识库模块路由：/api/v1/knowledge-bases。"""

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.core.config import settings
from app.dependencies import CurrentTeamAdminOrLead, CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.knowledge import (
    DocumentCreateData,
    DocumentIdRequest,
    DocumentItem,
    DocumentPageData,
    DocumentPageRequest,
    KnowledgeCreateData,
    KnowledgeCreateRequest,
    KnowledgeIdRequest,
    KnowledgeItem,
    KnowledgePageData,
    KnowledgePageRequest,
    KnowledgeUpdateRequest,
)
from app.services.knowledge_service import knowledge_service

router = APIRouter(
    prefix=settings.api_v1_prefix + "/knowledge-bases",
    tags=["知识库"],
)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def knowledge_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="knowledge-bases", detail="知识库管理路由已就绪")
    )


@router.post(
    "/create",
    response_model=ApiResponse[KnowledgeCreateData],
    summary="创建知识库",
    status_code=201,
)
async def create_knowledge_base(
    body: KnowledgeCreateRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[KnowledgeCreateData]:
    data = await knowledge_service.create(db, user, body)
    return ApiResponse(message="创建成功", data=data)


@router.post(
    "/page",
    response_model=ApiResponse[KnowledgePageData],
    summary="分页查询知识库",
)
async def page_knowledge_bases(
    body: KnowledgePageRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[KnowledgePageData]:
    data = await knowledge_service.page(db, user, body)
    return ApiResponse(data=data)


@router.post(
    "/getById",
    response_model=ApiResponse[KnowledgeItem],
    summary="获取知识库详情",
)
async def get_knowledge_base_by_id(
    body: KnowledgeIdRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[KnowledgeItem]:
    data = await knowledge_service.get_by_id(db, user, body)
    return ApiResponse(data=data)


@router.post(
    "/update",
    response_model=ApiResponse[None],
    summary="修改知识库",
)
async def update_knowledge_base(
    body: KnowledgeUpdateRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[None]:
    await knowledge_service.update(db, user, body)
    return ApiResponse(message="更新成功")


@router.post(
    "/delete",
    response_model=ApiResponse[None],
    summary="删除知识库",
)
async def delete_knowledge_base(
    body: KnowledgeIdRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[None]:
    await knowledge_service.delete(db, user, body)
    return ApiResponse(message="删除成功")


@router.post(
    "/createDocuments",
    response_model=ApiResponse[DocumentCreateData],
    summary="上传文档",
    status_code=201,
)
async def create_documents(
    kb_id: Annotated[int, Form(description="知识库 ID")],
    file: Annotated[
        UploadFile,
        File(description="选择要上传的文档（支持 pdf / docx / md / txt，最大 20MB）"),
    ],
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[DocumentCreateData]:
    data = await knowledge_service.create_document(db, user, kb_id=kb_id, file=file)
    return ApiResponse(message="上传成功", data=data)


@router.post(
    "/getDocumentById",
    response_model=ApiResponse[DocumentItem],
    summary="获取文档详情",
)
async def get_document_by_id(
    body: DocumentIdRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[DocumentItem]:
    data = await knowledge_service.get_document_by_id(db, user, body)
    return ApiResponse(data=data)


@router.post(
    "/pageDocuments",
    response_model=ApiResponse[DocumentPageData],
    summary="分页查询知识库文档",
)
async def page_documents(
    body: DocumentPageRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[DocumentPageData]:
    data = await knowledge_service.page_documents(db, user, body)
    return ApiResponse(data=data)


@router.post(
    "/deleteDocumentById",
    response_model=ApiResponse[None],
    summary="删除文档",
)
async def delete_document_by_id(
    body: DocumentIdRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[None]:
    await knowledge_service.delete_document_by_id(db, user, body)
    return ApiResponse(message="删除成功")
