"""文档生成核心：内置模板、Prompt 组装、导出。"""

from app.templateDoc.docExport import DocExporter
from app.templateDoc.template import (
    AI_DISCLAIMER,
    BUILTIN_TEMPLATES,
    DocType,
    DocumentGenerationService,
    document_generation_service,
    infer_doc_type,
)

__all__ = [
    "AI_DISCLAIMER",
    "BUILTIN_TEMPLATES",
    "DocExporter",
    "DocType",
    "DocumentGenerationService",
    "document_generation_service",
    "infer_doc_type",
]
