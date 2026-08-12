"""LangGraph 代码生成流水线：意图解析 → 规范注入 → 生成 → 安全过滤 → 格式化。"""

from __future__ import annotations

import logging
from typing import Any, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.code_analysis_service import (
    SPEC_PLACEHOLDER,
    code_analysis_service,
)
from app.services.code_generation_service import (
    DISCLAIMER,
    code_generation_service,
    format_generation_answer,
)
from app.services.code_parser import CodeParser
from app.services.code_safety_filter import filter_code

logger = logging.getLogger(__name__)

_parser = CodeParser()


class CodeGenState(TypedDict):
    """代码生成图状态。"""

    message: str
    conversation_id: int
    team_id: NotRequired[int | None]
    kb_ids: NotRequired[list[int]]
    content_type: NotRequired[str | None]
    mode: str  # generate | edit
    language: str
    framework: str
    design_pattern: str
    requirements: str
    constraints: list[str]
    reference_code: str
    spec_text: str
    sources: list[dict[str, Any]]
    raw_code: str
    usage: str
    dependencies: list[str]
    safety_flags: list[dict[str, Any]]
    answer: str
    status: str
    spec_injected: bool
    disclaimer: str


async def intent_parse_node(state: CodeGenState) -> dict[str, Any]:
    """节点1：抽取参考代码 + 解析语言/框架/模式等约束。"""
    message = state.get("message") or ""
    content_type = state.get("content_type")
    reference = (state.get("reference_code") or "").strip()
    if not reference:
        reference, _ = _parser.extract_code(message, content_type=content_type)

    has_reference = bool(reference)
    hint: Literal["generate", "edit"] = (
        "edit" if has_reference else "generate"
    )
    # 路由预填的 mode 优先作为 hint
    preset = str(state.get("mode") or "").strip().lower()
    if preset in ("generate", "edit"):
        hint = preset  # type: ignore[assignment]
        if not has_reference:
            hint = "generate"

    parsed = await code_generation_service.parse_intent(
        message,
        has_reference=has_reference,
        hint_mode=hint,
    )

    language = parsed["language"]
    if not language and reference:
        detected = _parser.detect_language(reference, None)
        language = detected or ""

    logger.info(
        "code_gen intent_parse conversation_id=%s mode=%s language=%s has_ref=%s",
        state.get("conversation_id"),
        parsed["mode"],
        language,
        has_reference,
    )
    return {
        "mode": parsed["mode"],
        "language": language,
        "framework": parsed["framework"],
        "design_pattern": parsed["design_pattern"],
        "requirements": parsed["requirements"] or message.strip()[:200],
        "constraints": parsed["constraints"],
        "reference_code": reference,
    }


async def spec_inject_node(state: CodeGenState) -> dict[str, Any]:
    """节点2：按 team_id 检索团队编码规范并注入。"""
    language = (state.get("language") or "通用").strip() or "通用"
    team_id = state.get("team_id")
    kb_ids = list(state.get("kb_ids") or [])

    spec_text, sources = await code_analysis_service.fetch_coding_spec(
        team_id=team_id,
        kb_ids=kb_ids,
        language=language,
    )
    injected = bool(spec_text) and spec_text != SPEC_PLACEHOLDER
    logger.info(
        "code_gen spec_inject conversation_id=%s injected=%s sources=%s",
        state.get("conversation_id"),
        injected,
        len(sources),
    )
    return {
        "spec_text": spec_text or SPEC_PLACEHOLDER,
        "sources": sources,
        "spec_injected": injected,
    }


async def code_generate_node(state: CodeGenState) -> dict[str, Any]:
    """节点3：调用大模型生成/改写代码。"""
    try:
        result = await code_generation_service.generate_code(
            mode=str(state.get("mode") or "generate"),
            language=str(state.get("language") or ""),
            framework=str(state.get("framework") or ""),
            design_pattern=str(state.get("design_pattern") or ""),
            requirements=str(state.get("requirements") or ""),
            constraints=list(state.get("constraints") or []),
            reference_code=str(state.get("reference_code") or ""),
            spec_text=str(state.get("spec_text") or SPEC_PLACEHOLDER),
        )
    except Exception as exc:
        logger.exception(
            "code_gen 生成失败 conversation_id=%s: %s",
            state.get("conversation_id"),
            exc,
        )
        return {
            "raw_code": "",
            "usage": "代码生成暂时失败，请稍后重试。",
            "dependencies": [],
            "language": state.get("language") or "text",
            "status": "error",
        }

    language = result["language"] or state.get("language") or "text"
    if not result["code"]:
        return {
            "raw_code": "",
            "usage": result["usage"],
            "dependencies": result["dependencies"],
            "language": language,
            "status": "error",
        }

    logger.info(
        "code_gen generate conversation_id=%s language=%s code_len=%s",
        state.get("conversation_id"),
        language,
        len(result["code"]),
    )
    return {
        "raw_code": result["code"],
        "usage": result["usage"],
        "dependencies": result["dependencies"],
        "language": language,
        "status": "ok",
    }


async def safety_filter_node(state: CodeGenState) -> dict[str, Any]:
    """节点4：安全过滤硬编码密钥与危险调用。"""
    raw = state.get("raw_code") or ""
    if not raw:
        return {"raw_code": "", "safety_flags": []}

    filtered, flags = filter_code(raw)
    if flags:
        logger.info(
            "code_gen safety_filter conversation_id=%s flags=%s",
            state.get("conversation_id"),
            len(flags),
        )
    return {"raw_code": filtered, "safety_flags": flags}


async def format_output_node(state: CodeGenState) -> dict[str, Any]:
    """节点5：格式化为对话 Markdown。"""
    if state.get("status") == "error" and not (state.get("raw_code") or "").strip():
        err = (state.get("usage") or "").strip() or "代码生成暂时失败，请稍后重试。"
        return {"answer": err, "status": "error"}

    payload = {
        "mode": state.get("mode") or "generate",
        "language": state.get("language") or "text",
        "code": state.get("raw_code") or "",
        "usage": state.get("usage") or "",
        "dependencies": list(state.get("dependencies") or []),
        "safety_flags": list(state.get("safety_flags") or []),
        "spec_injected": bool(state.get("spec_injected")),
        "disclaimer": state.get("disclaimer") or DISCLAIMER,
    }
    answer = format_generation_answer(payload)
    return {"answer": answer, "status": state.get("status") or "ok"}


def build_code_generation_graph():
    """构建并编译代码生成图。"""
    graph = StateGraph(CodeGenState)
    graph.add_node("intent_parse", intent_parse_node)
    graph.add_node("spec_inject", spec_inject_node)
    graph.add_node("code_generate", code_generate_node)
    graph.add_node("safety_filter", safety_filter_node)
    graph.add_node("format_output", format_output_node)

    graph.add_edge(START, "intent_parse")
    graph.add_edge("intent_parse", "spec_inject")
    graph.add_edge("spec_inject", "code_generate")
    graph.add_edge("code_generate", "safety_filter")
    graph.add_edge("safety_filter", "format_output")
    graph.add_edge("format_output", END)
    return graph.compile()


code_generation_graph = build_code_generation_graph()
