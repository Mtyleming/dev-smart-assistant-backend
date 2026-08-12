"""代码生成服务：子模式判定、提示词、LLM 调用、Markdown 格式化、跑图入口。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from app.services.ai.llm_client import llm_client
from app.services.code_parser import CodeParser

logger = logging.getLogger(__name__)

CodeSubMode = Literal["analyze", "generate", "edit"]

DISCLAIMER = "由 AI 生成，建议 Code Review 后使用"
SPEC_PLACEHOLDER = "未检测到团队编码规范"

_ANALYZE_KEYWORDS = (
    "解读",
    "解释",
    "分析",
    "审查",
    "评审",
    "看看这段",
    "看下这段",
    "什么意思",
    "讲解",
    "说明这段",
    "帮我看",
    "有没有问题",
    "有哪些问题",
)

_EDIT_KEYWORDS = (
    "改一下",
    "帮我改",
    "修改",
    "重构",
    "优化这段",
    "优化这个",
    "补全",
    "修复",
    "重写",
    "改成",
    "改写",
    "基于这段",
    "根据这段",
    "按要求改",
    "加上",
    "删掉",
    "替换",
)

_GENERATE_KEYWORDS = (
    "帮我写",
    "帮我生成",
    "请生成",
    "生成一段",
    "生成一个",
    "生成代码",
    "写一段",
    "写一个",
    "写个",
    "实现一个",
    "实现一段",
    "给我写",
    "创建一段",
    "创建一个",
)

_ANALYZE_RE = re.compile("|".join(re.escape(k) for k in _ANALYZE_KEYWORDS))
_EDIT_RE = re.compile("|".join(re.escape(k) for k in _EDIT_KEYWORDS))
_GENERATE_RE = re.compile("|".join(re.escape(k) for k in _GENERATE_KEYWORDS))

INTENT_PARSE_SYSTEM_PROMPT = (
    "你是代码需求解析器。根据用户消息提取生成/改写所需参数。"
    "只输出一行 JSON，不要 Markdown，不要解释。"
)

INTENT_PARSE_HUMAN_TEMPLATE = (
    "用户消息：\n{message}\n\n"
    "是否已抽出参考代码：{has_reference}\n"
    "预判子模式：{hint_mode}\n\n"
    "请输出 JSON，字段：\n"
    '- mode: "generate" 或 "edit"\n'
    "- language: 目标语言（如 python / javascript），未知则空字符串\n"
    "- framework: 框架（如 FastAPI / React），无则空字符串\n"
    "- design_pattern: 设计模式（如 factory），无则空字符串\n"
    "- requirements: 需求摘要（一句话）\n"
    "- constraints: 其它约束数组（字符串列表）\n"
)

CODE_GENERATE_SYSTEM_TEMPLATE = (
    "你是资深软件工程师，按用户需求生成或改写代码。\n"
    "必须遵守以下团队编码规范（若提示未检测到规范，则遵循通用最佳实践）：\n"
    "-----\n{spec}\n-----\n"
    "安全约束：禁止硬编码密钥/密码/Token；禁止 os.system、"
    "subprocess(shell=True)、eval、exec、pickle.loads 等危险调用；"
    "敏感配置一律用环境变量。\n"
    "只输出 JSON，不要 Markdown 标题或其它解释。"
)

CODE_GENERATE_HUMAN_TEMPLATE = (
    "## 模式\n{mode}\n\n"
    "## 目标语言\n{language}\n\n"
    "## 框架\n{framework}\n\n"
    "## 设计模式\n{design_pattern}\n\n"
    "## 需求\n{requirements}\n\n"
    "## 其它约束\n{constraints}\n\n"
    "## 参考代码（edit 模式时必须基于此修改）\n"
    "```{language}\n{reference_code}\n```\n\n"
    "请输出 JSON，字段：\n"
    "1. code: 完整可运行或可粘贴的代码字符串\n"
    "2. language: 代码语言\n"
    "3. usage: 使用说明（字符串）\n"
    "4. dependencies: 依赖说明列表（字符串数组）\n"
)

def resolve_mode(message: str, *, has_code: bool) -> CodeSubMode:
    """根据消息与是否抽出代码，判定子模式 analyze / generate / edit。"""
    text = message or ""
    if not has_code:
        return "generate"

    edit_hit = bool(_EDIT_RE.search(text))
    analyze_hit = bool(_ANALYZE_RE.search(text))
    generate_hit = bool(_GENERATE_RE.search(text))

    if edit_hit and not analyze_hit:
        return "edit"
    if analyze_hit and not edit_hit and not generate_hit:
        return "analyze"
    if edit_hit and analyze_hit:
        # 「看看再改」优先走改写
        return "edit"
    if generate_hit:
        # 有参考代码又要写/生成 → 按改写处理
        return "edit"
    # 有代码且无明确改写/生成词 → 保持原解读行为
    return "analyze"


def _extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出中提取 JSON 对象。"""
    content = (text or "").strip()
    if not content:
        raise json.JSONDecodeError("空响应", content, 0)

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE)
    if fence:
        parsed = json.loads(fence.group(1).strip())
        if isinstance(parsed, dict):
            return parsed

    # 平衡括号扫描
    start = content.find("{")
    if start >= 0:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(content)):
            ch = content[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    parsed = json.loads(content[start : i + 1])
                    if isinstance(parsed, dict):
                        return parsed
                    break

    raise json.JSONDecodeError("未找到合法 JSON 对象", content, 0)


def normalize_intent_result(
    raw: dict[str, Any],
    *,
    hint_mode: Literal["generate", "edit"],
    has_reference: bool,
) -> dict[str, Any]:
    """规范化意图解析结果。"""
    mode = str(raw.get("mode") or hint_mode).strip().lower()
    if mode not in ("generate", "edit"):
        mode = hint_mode
    if not has_reference:
        mode = "generate"
    elif mode == "generate" and has_reference:
        # 图内只处理 generate/edit；有参考代码时纠正为 edit
        mode = "edit"

    constraints = raw.get("constraints")
    if not isinstance(constraints, list):
        constraints = []
    constraints = [str(c).strip() for c in constraints if str(c).strip()]

    return {
        "mode": mode,
        "language": str(raw.get("language") or "").strip().lower(),
        "framework": str(raw.get("framework") or "").strip(),
        "design_pattern": str(raw.get("design_pattern") or "").strip(),
        "requirements": str(raw.get("requirements") or "").strip(),
        "constraints": constraints,
    }


def normalize_generate_result(raw: dict[str, Any], *, fallback_language: str) -> dict[str, Any]:
    """规范化代码生成 JSON。"""
    deps = raw.get("dependencies")
    if not isinstance(deps, list):
        deps = []
    deps = [str(d).strip() for d in deps if str(d).strip()]
    language = str(raw.get("language") or fallback_language or "text").strip().lower()
    code = str(raw.get("code") or "").strip()
    usage = str(raw.get("usage") or "").strip()
    return {
        "code": code,
        "language": language or "text",
        "usage": usage or "按需粘贴到项目中使用。",
        "dependencies": deps,
    }


def format_generation_answer(result: dict[str, Any]) -> str:
    """将生成结果格式化为中文 Markdown。"""
    mode = str(result.get("mode") or "generate")
    language = str(result.get("language") or "text")
    code = str(result.get("code") or "").rstrip()
    usage = str(result.get("usage") or "").strip() or "（无）"
    deps = result.get("dependencies") if isinstance(result.get("dependencies"), list) else []
    flags = result.get("safety_flags") if isinstance(result.get("safety_flags"), list) else []
    disclaimer = str(result.get("disclaimer") or DISCLAIMER).strip()
    title = "改写代码" if mode == "edit" else "生成代码"

    lines: list[str] = [
        f"## {title}（{language}）",
        "",
    ]
    if result.get("spec_injected"):
        lines.append("> 已对照团队知识库中的编码规范生成。")
        lines.append("")

    lines.extend(
        [
            f"```{language}",
            code if code else "# （未生成有效代码）",
            "```",
            "",
            "### 使用说明",
            usage,
            "",
            "### 依赖说明",
        ]
    )
    if not deps:
        lines.append("- 无额外依赖")
    else:
        for item in deps:
            lines.append(f"- {item}")

    if flags:
        lines.extend(["", "### 安全过滤"])
        for flag in flags:
            if isinstance(flag, dict):
                detail = str(flag.get("detail") or flag.get("pattern") or "已过滤")
                lines.append(f"- {detail}")
            else:
                lines.append(f"- {flag}")

    if disclaimer:
        lines.extend(["", f"> {disclaimer}"])

    return "\n".join(lines).strip()


class CodeGenerationService:
    """代码生成 / 改写编排。"""

    def __init__(self, parser: CodeParser | None = None) -> None:
        self.parser = parser or CodeParser()

    async def parse_intent(
        self,
        message: str,
        *,
        has_reference: bool,
        hint_mode: Literal["generate", "edit"],
    ) -> dict[str, Any]:
        """调用 LLM 解析语言、框架、模式等约束。"""
        human = INTENT_PARSE_HUMAN_TEMPLATE.format(
            message=message or "",
            has_reference="是" if has_reference else "否",
            hint_mode=hint_mode,
        )
        try:
            raw_text = await llm_client.chat(
                [{"role": "user", "content": human}],
                system_prompt=INTENT_PARSE_SYSTEM_PROMPT,
            )
            raw = _extract_json_object(raw_text)
            return normalize_intent_result(
                raw, hint_mode=hint_mode, has_reference=has_reference
            )
        except Exception as exc:
            logger.warning("意图解析失败，使用兜底参数: %s", exc)
            return normalize_intent_result(
                {
                    "mode": hint_mode,
                    "language": "",
                    "framework": "",
                    "design_pattern": "",
                    "requirements": (message or "").strip()[:200],
                    "constraints": [],
                },
                hint_mode=hint_mode,
                has_reference=has_reference,
            )

    async def generate_code(
        self,
        *,
        mode: str,
        language: str,
        framework: str,
        design_pattern: str,
        requirements: str,
        constraints: list[str],
        reference_code: str,
        spec_text: str,
    ) -> dict[str, Any]:
        """调用 LLM 生成/改写代码。"""
        lang = language or "text"
        system = CODE_GENERATE_SYSTEM_TEMPLATE.format(
            spec=spec_text or SPEC_PLACEHOLDER
        )
        constraints_text = (
            "\n".join(f"- {c}" for c in constraints) if constraints else "- （无）"
        )
        human = CODE_GENERATE_HUMAN_TEMPLATE.format(
            mode=mode,
            language=lang,
            framework=framework or "（未指定）",
            design_pattern=design_pattern or "（未指定）",
            requirements=requirements or "（见用户原文）",
            constraints=constraints_text,
            reference_code=reference_code or "（无参考代码）",
        )
        raw_text = await llm_client.chat(
            [{"role": "user", "content": human}],
            system_prompt=system,
        )
        try:
            raw = _extract_json_object(raw_text)
            return normalize_generate_result(raw, fallback_language=lang)
        except Exception as exc:
            logger.warning("代码生成 JSON 解析失败，尝试抽取围栏代码: %s", exc)
            # 兜底：从 Markdown 围栏抽代码
            from app.services.code_parser import CodeParser as _P

            code, fence_lang = _P().extract_code(raw_text)
            return normalize_generate_result(
                {
                    "code": code or raw_text,
                    "language": fence_lang or lang,
                    "usage": "模型未返回结构化说明，请直接使用上方代码。",
                    "dependencies": [],
                },
                fallback_language=lang,
            )

    async def generate(
        self,
        message: str,
        conversation_id: int,
        *,
        team_id: int | None = None,
        kb_ids: list[int] | None = None,
        content_type: str | None = None,
        hint_mode: Literal["generate", "edit"] | None = None,
    ) -> dict[str, Any]:
        """跑完整生成流水线，返回路由可用结果。"""
        from app.services.ai.code_generation_graph import code_generation_graph

        code, _fence = self.parser.extract_code(message, content_type=content_type)
        has_code = bool(code)
        resolved = hint_mode or (
            "edit" if has_code else "generate"
        )
        if resolved == "analyze":
            resolved = "edit" if has_code else "generate"

        initial = {
            "message": message or "",
            "conversation_id": conversation_id,
            "team_id": team_id,
            "kb_ids": list(kb_ids or []),
            "content_type": content_type,
            "mode": resolved,
            "language": "",
            "framework": "",
            "design_pattern": "",
            "requirements": "",
            "constraints": [],
            "reference_code": code,
            "spec_text": SPEC_PLACEHOLDER,
            "sources": [],
            "raw_code": "",
            "usage": "",
            "dependencies": [],
            "safety_flags": [],
            "answer": "",
            "status": "ok",
            "spec_injected": False,
            "disclaimer": DISCLAIMER,
        }
        final = await code_generation_graph.ainvoke(initial)
        return {
            "intent": "code_request",
            "status": final.get("status") or "ok",
            "answer": final.get("answer") or "",
            "sources": final.get("sources") or [],
            "language": final.get("language"),
            "mode": final.get("mode"),
            "spec_injected": bool(final.get("spec_injected")),
            "safety_flags": final.get("safety_flags") or [],
        }


code_generation_service = CodeGenerationService()
