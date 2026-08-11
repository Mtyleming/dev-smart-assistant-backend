"""代码分析服务：语言检测、结构化、检索团队编码规范、调用大模型深度解读。"""

from __future__ import annotations

import logging
from typing import Any

from app.services.ai.llm_client import llm_client
from app.services.ai.rag_pipeline import rag_pipeline
from app.services.code_parser import CodeParser

logger = logging.getLogger(__name__)

MAX_CODE_LINES = 2000
# 规范注入提示词时的大致长度上限（字符），避免挤占代码上下文
MAX_SPEC_CHARS = 6000

CODE_ANALYSIS_SYSTEM_PROMPT = (
    "你是一位资深代码审查专家。请对以下代码进行深度分析。"
    "若提供了「团队编码规范」，审查时必须对照规范指出不符合项，并给出符合规范的改法。"
    "只输出 JSON，不要 Markdown 标题或其它解释文字。"
)

SPEC_PLACEHOLDER = "未检测到团队编码规范"

HUMAN_PROMPT_TEMPLATE = (
    "## 代码语言\n{language}\n\n"
    "## 团队编码规范\n{spec}\n\n"
    "## 代码内容\n```{language}\n{code}\n```\n\n"
    "请输出 JSON 格式的分析结果，包含以下字段：\n"
    "1. summary: 功能概述（50字内）\n"
    "2. logic_explanation: 逐函数/逐块逻辑说明（字符串）\n"
    "3. data_flow: 数据流向描述（字符串）\n"
    "4. issues: 潜在问题列表，每项包含 description、risk_level（高/中/低）、suggestion\n"
    "5. optimization: 优化建议列表（字符串数组）"
)


def _build_spec_query(language: str) -> str:
    """构造用于检索团队编码规范的查询语句。"""
    lang = (language or "").strip() or "通用"
    return (
        f"{lang} 团队编码规范 命名规范 注释规范 Git 规范 代码风格 "
        f"coding standards style guide"
    )


def _chunks_to_spec_text(chunks: list[dict[str, Any]]) -> str:
    """将检索切块拼成规范正文，超长则截断。"""
    parts: list[str] = []
    total = 0
    for order, chunk in enumerate(chunks, start=1):
        content = str(chunk.get("content") or "").strip()
        if not content:
            continue
        document_id = chunk.get("document_id")
        block = f"[规范片段{order}|document_id={document_id}]\n{content}"
        if total + len(block) > MAX_SPEC_CHARS:
            remain = MAX_SPEC_CHARS - total
            if remain > 100:
                parts.append(block[:remain] + "…")
            break
        parts.append(block)
        total += len(block) + 2
    return "\n\n".join(parts).strip()


def _chunks_to_sources(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """规范切块转为可落库 / 返回的 sources。"""
    sources: list[dict[str, Any]] = []
    for order, chunk in enumerate(chunks, start=1):
        sources.append(
            {
                "ref": order,
                "document_id": chunk.get("document_id"),
                "chunk_index": chunk.get("chunk_index"),
                "knowledge_base_id": chunk.get("knowledge_base_id"),
                "score": chunk.get("score"),
                "chunk_id": chunk.get("chunk_id"),
                "content": str(chunk.get("content") or ""),
                "kind": "coding_spec",
            }
        )
    return sources


class CodeAnalysisService:
    """粘贴代码 → 解析 → 检索规范 → 模型分析 → 结构化结果。"""

    def __init__(self, parser: CodeParser | None = None) -> None:
        self.parser = parser or CodeParser()

    async def fetch_coding_spec(
        self,
        *,
        team_id: int | None,
        kb_ids: list[int] | None,
        language: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """从团队知识库检索编码规范。

        Returns:
            (spec_text, sources)。未命中或无 team_id 时返回占位文案与空 sources。
        """
        if team_id is None:
            return SPEC_PLACEHOLDER, []

        query = _build_spec_query(language)
        try:
            retrieved = await rag_pipeline.retrieve(
                query,
                team_id=int(team_id),
                kb_ids=list(kb_ids or []),
            )
        except Exception as exc:
            logger.warning(
                "检索团队编码规范失败 team_id=%s language=%s: %s",
                team_id,
                language,
                exc,
            )
            return SPEC_PLACEHOLDER, []

        if not retrieved.get("use_retrieval"):
            logger.info(
                "未命中团队编码规范 team_id=%s language=%s confidence=%s",
                team_id,
                language,
                retrieved.get("confidence"),
            )
            return SPEC_PLACEHOLDER, []

        chunks = list(retrieved.get("chunks") or [])
        spec_text = _chunks_to_spec_text(chunks)
        if not spec_text:
            return SPEC_PLACEHOLDER, []

        sources = _chunks_to_sources(chunks)
        logger.info(
            "已注入团队编码规范 team_id=%s language=%s chunks=%s chars=%s",
            team_id,
            language,
            len(chunks),
            len(spec_text),
        )
        return spec_text, sources

    async def analyze(
        self,
        message: str,
        *,
        content_type: str | None = None,
        code: str | None = None,
        fence_lang: str | None = None,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """分析用户消息中的代码。

        Raises:
            ValueError: 行数超限、抽不出代码、或不支持的语言。
        """
        if code is None:
            code, fence_lang = self.parser.extract_code(
                message, content_type=content_type
            )
        code = (code or "").strip()
        if not code:
            raise ValueError("未检测到可分析的代码，请粘贴代码后再试")

        if len(code.splitlines()) > MAX_CODE_LINES:
            raise ValueError(f"代码行数超过 {MAX_CODE_LINES} 行，请分段提交")

        language = self.parser.detect_language(code, fence_lang)
        if not language:
            raise ValueError("暂不支持该语言")

        structure = self.parser.parse_structure(code, language)
        spec_text, spec_sources = await self.fetch_coding_spec(
            team_id=team_id,
            kb_ids=kb_ids,
            language=language,
        )

        human = HUMAN_PROMPT_TEMPLATE.format(
            language=language,
            spec=spec_text,
            code=code,
        )

        logger.info(
            "代码分析开始 language=%s lines=%s funcs=%s has_spec=%s",
            language,
            structure.get("line_count"),
            len(structure.get("functions") or []),
            spec_text != SPEC_PLACEHOLDER,
        )

        raw = await llm_client.chat(
            [{"role": "user", "content": human}],
            system_prompt=CODE_ANALYSIS_SYSTEM_PROMPT,
        )
        result = self.parser.parse_llm_response(raw)
        result["language"] = language
        result["structure"] = structure
        result["spec_injected"] = spec_text != SPEC_PLACEHOLDER
        result["sources"] = spec_sources
        result["disclaimer"] = "由 AI 生成，建议 Code Review 后使用"
        return result

    def format_answer(self, result: dict[str, Any]) -> str:
        """将结构化分析结果格式化为中文 Markdown，供对话展示。"""
        language = result.get("language") or "unknown"
        summary = str(result.get("summary") or "").strip() or "（无概述）"
        logic = str(result.get("logic_explanation") or "").strip() or "（无）"
        data_flow = str(result.get("data_flow") or "").strip() or "（无）"
        disclaimer = str(result.get("disclaimer") or "").strip()
        structure = (
            result.get("structure")
            if isinstance(result.get("structure"), dict)
            else {}
        )

        lines: list[str] = [
            f"## 代码解读（{language}）",
            "",
        ]
        if result.get("spec_injected"):
            lines.append("> 已对照团队知识库中的编码规范进行分析。")
            lines.append("")
        lines.extend(
            [
                f"**功能概述**：{summary}",
                "",
            ]
        )

        funcs = structure.get("functions") or []
        classes = structure.get("classes") or []
        if funcs or classes:
            lines.append("**结构概览**：")
            if classes:
                lines.append(f"- 类：{', '.join(str(c) for c in classes)}")
            if funcs:
                lines.append(f"- 函数/方法：{', '.join(str(f) for f in funcs)}")
            lines.append("")

        lines.extend(
            [
                "### 逻辑说明",
                logic,
                "",
                "### 数据流向",
                data_flow,
                "",
                "### 潜在问题",
            ]
        )

        issues = result.get("issues") if isinstance(result.get("issues"), list) else []
        if not issues:
            lines.append("- 未发现明显问题")
        else:
            for item in issues:
                if isinstance(item, dict):
                    desc = str(item.get("description") or "").strip() or "（未描述）"
                    risk = str(item.get("risk_level") or "中").strip()
                    suggestion = str(item.get("suggestion") or "").strip()
                    line = f"- [{risk}] {desc}"
                    if suggestion:
                        line += f"；建议：{suggestion}"
                    lines.append(line)
                else:
                    lines.append(f"- {item}")

        lines.extend(["", "### 优化建议"])
        optimization = (
            result.get("optimization")
            if isinstance(result.get("optimization"), list)
            else []
        )
        if not optimization:
            lines.append("- 暂无额外优化建议")
        else:
            for tip in optimization:
                lines.append(f"- {tip}")

        if disclaimer:
            lines.extend(["", f"> {disclaimer}"])

        return "\n".join(lines).strip()


code_analysis_service = CodeAnalysisService()
