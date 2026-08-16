"""文档生成：加载模板、检索风格、调用通义千问、附加 AI 声明。"""

from __future__ import annotations

import logging
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFoundError
from app.models.base_models import DocumentTemplateType
from app.repositories.document_template_repo import document_template_repo
from app.services.ai.llm_client import llm_client
from app.services.knowledge_service import knowledge_service
from app.templateDoc.docExport import DocExporter, doc_exporter

logger = logging.getLogger(__name__)

# 生成结果固定头部，提醒人工审阅
AI_DISCLAIMER = "由 AI 生成，建议人工审阅后发布"
AI_HEADER = f"> {AI_DISCLAIMER}\n\n"
STYLE_PLACEHOLDER = "未检测到团队文档风格参考，使用通用技术文档风格"
MAX_INPUT_CHARS = 20_000


class DocType(str, Enum):
    """文档类型，与 document_templates.type 枚举对齐。"""

    API_DOC = "api_doc"
    MODULE_DOC = "module_doc"
    CHANGELOG = "changelog"
    GETTING_STARTED = "getting_started"
    CUSTOM = "custom"


# 代码内置默认模板：库中无自定义、也无系统内置行时使用
# 占位符与库内模板一致，使用 {{name}} 形式，避免和 Python 格式化语法混淆
BUILTIN_TEMPLATES: dict[DocType, str] = {
    DocType.API_DOC: """
## 接口说明
{{summary}}

## 请求参数
| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
{{request_params}}

## 响应参数
| 字段名 | 类型 | 说明 |
|---|---|---|
{{response_params}}

## 请求示例
{{request_example}}

## 响应示例
{{response_example}}

## 错误码
| 错误码 | 说明 |
|---|---|
{{error_codes}}
""",
    DocType.MODULE_DOC: """
## 模块概述
{{summary}}

## 核心功能
{{features}}

## 依赖关系
{{dependencies}}

## 使用示例
{{usage_example}}
""",
    DocType.CHANGELOG: """
## 版本 {{version}}

### 变更类型：{{change_type}}

### 变更详情
{{details}}

### 影响范围
{{impact}}
""",
    DocType.GETTING_STARTED: """
## 项目简介
{{summary}}

## 环境要求
{{requirements}}

## 安装步骤
{{install_steps}}

## 快速上手
{{quick_start}}

## 常见问题
{{faq}}
""",
    DocType.CUSTOM: """
## 标题
{{title}}

## 正文
{{body}}
""",
}

_DOC_TYPE_KEYWORDS: list[tuple[DocType, tuple[str, ...]]] = [
    (DocType.API_DOC, ("接口", "api", "endpoint", "openapi", "swagger")),
    (DocType.CHANGELOG, ("变更日志", "changelog", "更新日志", "release note")),
    (
        DocType.GETTING_STARTED,
        ("快速开始", "入门", "getting started", "readme", "安装步骤"),
    ),
    (DocType.MODULE_DOC, ("模块", "设计文档", "说明文档")),
]


def parse_doc_type(value: str | DocType | DocumentTemplateType) -> DocType:
    """把字符串/枚举解析为 DocType，无法识别时按模块文档处理。"""
    if isinstance(value, DocType):
        return value
    raw = value.value if isinstance(value, DocumentTemplateType) else str(value or "")
    raw = raw.strip().lower()
    for item in DocType:
        if item.value == raw:
            return item
    logger.warning("未知文档类型 %s，回退为 module_doc", value)
    return DocType.MODULE_DOC


def infer_doc_type(message: str) -> DocType:
    """从自然语言粗略推断文档类型（对话入口用）。"""
    text = (message or "").lower()
    for doc_type, keywords in _DOC_TYPE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return doc_type
    return DocType.MODULE_DOC


def _resolve_builtin_text(doc_type: DocType) -> str:
    """取代码内置模板正文。"""
    return BUILTIN_TEMPLATES.get(doc_type, BUILTIN_TEMPLATES[DocType.MODULE_DOC]).strip()


def ensure_ai_header(content: str) -> str:
    """保证正文以 AI 声明开头（模型若已输出则不重复）。"""
    text = (content or "").strip()
    if text.startswith(f"> {AI_DISCLAIMER}") or text.startswith(AI_DISCLAIMER):
        if not text.startswith(">"):
            return f"> {text}"
        return text
    return AI_HEADER + text


class DocumentGenerationService:
    """文档生成编排：模板 → 风格参考 → 通义千问 → 声明头 / 导出。"""

    def __init__(self, exporter: DocExporter | None = None) -> None:
        self.exporter = exporter or doc_exporter

    async def generate(
        self,
        db: AsyncSession,
        doc_type: DocType | str,
        input_content: str,
        team_id: int | str,
        is_code: bool = False,
        kb_ids: list[int] | None = None,
        template_id: int | None = None,
    ) -> dict:
        """根据类型与输入生成 Markdown 文档。

        Returns:
            content / doc_type / template_source / style_used
        """
        parsed_type = parse_doc_type(doc_type)
        team = int(team_id)
        content = (input_content or "").strip()
        if not content:
            raise AppException(code=40002, message="输入内容不能为空", status_code=400)
        if len(content) > MAX_INPUT_CHARS:
            logger.info(
                "输入过长已截断 team_id=%s doc_type=%s len=%s",
                team,
                parsed_type.value,
                len(content),
            )
            content = content[:MAX_INPUT_CHARS]

        prompt_template, template_source = await self._load_template(
            db, team, parsed_type, template_id=template_id
        )
        style_text, style_used = await self._load_style(
            team, parsed_type, content, kb_ids=kb_ids
        )

        system_prompt = (
            "你是一位专业技术文档工程师。请严格按以下模板结构生成文档内容。\n"
            "模板里的占位符是 {{name}} 这种双花括号形式，请替换为根据输入推断出的实际内容，"
            "不要原样输出占位符。\n\n"
            f"## 文档模板\n{prompt_template}\n\n"
            f"## 风格参考\n{style_text}\n\n"
            "输出要求：纯 Markdown 格式，不使用代码块包裹整体内容，单篇不超过 10000 字。"
            "不要在开头重复「由 AI 生成」声明。"
        )
        if is_code:
            human = (
                f"## 代码内容\n```\n{content}\n```\n\n"
                f"请生成 {parsed_type.value} 类型的技术文档。"
            )
        else:
            human = (
                f"## 需求描述\n{content}\n\n"
                f"请生成 {parsed_type.value} 类型的技术文档。"
            )

        logger.info(
            "开始生成文档 team_id=%s doc_type=%s source=%s style_used=%s is_code=%s",
            team,
            parsed_type.value,
            template_source,
            style_used,
            is_code,
        )
        try:
            raw = await llm_client.chat(
                [{"role": "user", "content": human}],
                system_prompt=system_prompt,
            )
        except Exception as exc:
            logger.exception(
                "通义千问生成文档失败 team_id=%s doc_type=%s: %s",
                team,
                parsed_type.value,
                exc,
            )
            raise AppException(
                code=50307,
                message="文档生成失败，请稍后重试或检查大模型配置",
                status_code=503,
            ) from exc

        markdown = ensure_ai_header(str(raw or "").strip())
        return {
            "content": markdown,
            "doc_type": parsed_type.value,
            "template_source": template_source,
            "style_used": style_used,
        }

    async def export(self, content: str, format: str, doc_type: str) -> bytes:
        """把 Markdown 导出为指定格式字节。"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_type = (doc_type or "document").strip() or "document"
        filename = f"{safe_type}_{timestamp}"
        try:
            return await self.exporter.export(content, format, filename)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("文档导出失败 format=%s: %s", format, exc)
            raise AppException(
                code=50308,
                message="文档导出失败，请稍后重试",
                status_code=503,
            ) from exc

    async def _load_template(
        self,
        db: AsyncSession,
        team_id: int,
        doc_type: DocType,
        template_id: int | None = None,
    ) -> tuple[str, str]:
        """优先指定模板，其次团队自定义，再次库内内置，最后代码默认模板。

        表唯一约束是 (team_id, name)，同一类型可以有多份自定义模板。
        未指定 template_id 时，取该类型最近更新的一份。
        """
        try:
            if template_id is not None:
                row = await document_template_repo.get_visible_by_id(
                    db, template_id, team_id
                )
                if row is None:
                    raise NotFoundError("模板不存在")
                text = (row.content or "").strip()
                if not text:
                    raise AppException(
                        code=40003,
                        message="指定模板内容为空，无法生成文档",
                        status_code=400,
                    )
                source = "builtin_db" if row.is_builtin else "custom"
                logger.info(
                    "使用指定模板 template_id=%s source=%s team_id=%s",
                    template_id,
                    source,
                    team_id,
                )
                return text, source

            same_type_count = await document_template_repo.count_custom_by_type(
                db, team_id, doc_type.value
            )
            if same_type_count > 1:
                logger.info(
                    "同类型有 %s 份自定义模板，将使用最近更新的一份；"
                    "如需指定请传 template_id。team_id=%s doc_type=%s",
                    same_type_count,
                    team_id,
                    doc_type.value,
                )

            row = await document_template_repo.get_active_template(
                db, team_id, doc_type.value
            )
        except AppException:
            raise
        except Exception as exc:
            logger.warning(
                "加载数据库模板失败，回退代码内置 team_id=%s doc_type=%s: %s",
                team_id,
                doc_type.value,
                exc,
            )
            return _resolve_builtin_text(doc_type), "builtin_code"

        if row is None:
            logger.info(
                "无库内模板，使用代码内置 team_id=%s doc_type=%s",
                team_id,
                doc_type.value,
            )
            return _resolve_builtin_text(doc_type), "builtin_code"

        text = (row.content or "").strip()
        if not text:
            logger.warning(
                "模板内容为空，回退代码内置 template_id=%s", row.id
            )
            return _resolve_builtin_text(doc_type), "builtin_code"

        if row.is_builtin:
            return text, "builtin_db"
        return text, "custom"

    async def _load_style(
        self,
        team_id: int,
        doc_type: DocType,
        input_content: str,
        kb_ids: list[int] | None = None,
    ) -> tuple[str, bool]:
        """从团队知识库检索同类文档切片作为写作风格参考。"""
        try:
            refs = await knowledge_service.search_similar_docs(
                team_id,
                doc_type.value,
                top_k=2,
                kb_ids=kb_ids,
                extra_query=input_content[:500],
            )
        except Exception as exc:
            logger.warning(
                "检索文档风格失败 team_id=%s doc_type=%s: %s",
                team_id,
                doc_type.value,
                exc,
            )
            return STYLE_PLACEHOLDER, False

        if not refs:
            return STYLE_PLACEHOLDER, False

        parts = [str(getattr(item, "content", "") or "").strip() for item in refs]
        parts = [p for p in parts if p]
        if not parts:
            return STYLE_PLACEHOLDER, False
        return "\n\n".join(parts), True


document_generation_service = DocumentGenerationService()
