"""代码分析服务：语言检测、结构化、调用大模型深度解读。"""

from __future__ import annotations

import logging
from typing import Any

from app.services.ai.llm_client import llm_client
from app.services.code_parser import CodeParser

logger = logging.getLogger(__name__)

MAX_CODE_LINES = 2000

CODE_ANALYSIS_SYSTEM_PROMPT = (
    "你是一位资深代码审查专家。请对以下代码进行深度分析。"
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


class CodeAnalysisService:
    """粘贴代码 → 解析 → 模型分析 → 结构化结果。"""

    def __init__(self, parser: CodeParser | None = None) -> None:
        self.parser = parser or CodeParser()

    async def analyze(
        self,
        message: str,
        *,
        content_type: str | None = None,
        code: str | None = None,
        fence_lang: str | None = None,
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
        spec_text = SPEC_PLACEHOLDER

        human = HUMAN_PROMPT_TEMPLATE.format(
            language=language,
            spec=spec_text,
            code=code,
        )

        logger.info(
            "代码分析开始 language=%s lines=%s funcs=%s",
            language,
            structure.get("line_count"),
            len(structure.get("functions") or []),
        )

        raw = await llm_client.chat(
            [{"role": "user", "content": human}],
            system_prompt=CODE_ANALYSIS_SYSTEM_PROMPT,
        )
        result = self.parser.parse_llm_response(raw)
        result["language"] = language
        result["structure"] = structure
        result["disclaimer"] = "由 AI 生成，建议 Code Review 后使用"
        return result

    def format_answer(self, result: dict[str, Any]) -> str:
        """将结构化分析结果格式化为中文 Markdown，供对话展示。"""
        language = result.get("language") or "unknown"
        summary = str(result.get("summary") or "").strip() or "（无概述）"
        logic = str(result.get("logic_explanation") or "").strip() or "（无）"
        data_flow = str(result.get("data_flow") or "").strip() or "（无）"
        disclaimer = str(result.get("disclaimer") or "").strip()
        structure = result.get("structure") if isinstance(result.get("structure"), dict) else {}

        lines: list[str] = [
            f"## 代码解读（{language}）",
            "",
            f"**功能概述**：{summary}",
            "",
        ]

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
