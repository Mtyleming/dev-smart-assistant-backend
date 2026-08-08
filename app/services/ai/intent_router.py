"""LangGraph 意图路由图：按意图分发到四个节点，节点内走策略模式。"""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.route import get_route_strategy, resolve_node_name


class IntentState(TypedDict):
    """意图路由图状态。"""

    message: str
    conversation_id: int
    intent: str
    confidence: float
    result: dict


def route_by_intent(
    state: IntentState,
) -> Literal["rag", "general", "code", "doc"]:
    """条件边：根据意图选择 LangGraph 节点。"""
    return resolve_node_name(state.get("intent") or "general_qa")  # type: ignore[return-value]


async def _run_strategy_node(state: IntentState, intent: str) -> dict:
    """统一节点执行：委托给对应意图策略（当前为占位）。"""
    strategy = get_route_strategy(intent)
    result = await strategy.run(state["message"], state["conversation_id"])
    return {"result": result}


async def rag_node(state: IntentState) -> dict:
    """知识库查询节点。"""
    return await _run_strategy_node(state, "knowledge_query")


async def general_node(state: IntentState) -> dict:
    """通用问答节点。"""
    return await _run_strategy_node(state, "general_qa")


async def code_node(state: IntentState) -> dict:
    """代码辅助节点。"""
    return await _run_strategy_node(state, "code_request")


async def doc_node(state: IntentState) -> dict:
    """文档生成节点。"""
    return await _run_strategy_node(state, "doc_generation")


def build_intent_graph():
    """构建并编译意图路由图。"""
    graph = StateGraph(IntentState)
    graph.add_node("rag", rag_node)
    graph.add_node("general", general_node)
    graph.add_node("code", code_node)
    graph.add_node("doc", doc_node)
    graph.add_conditional_edges(START, route_by_intent)
    graph.add_edge("rag", END)
    graph.add_edge("general", END)
    graph.add_edge("code", END)
    graph.add_edge("doc", END)
    return graph.compile()


intent_graph = build_intent_graph()
