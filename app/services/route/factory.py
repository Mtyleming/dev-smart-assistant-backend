"""意图路由策略工厂：按 intent 选择对应策略。"""

from __future__ import annotations

from app.services.route.base import IntentRouteStrategy
from app.services.route.code_request_route import CodeRequestRouteStrategy
from app.services.route.doc_generation_route import DocGenerationRouteStrategy
from app.services.route.general_qa_route import GeneralQaRouteStrategy
from app.services.route.knowledge_query_route import KnowledgeQueryRouteStrategy

# 四个意图 → 四个策略实例（与 LangGraph 四个节点一一对应）
_STRATEGIES: dict[str, IntentRouteStrategy] = {
    "knowledge_query": KnowledgeQueryRouteStrategy(),
    "general_qa": GeneralQaRouteStrategy(),
    "code_request": CodeRequestRouteStrategy(),
    "doc_generation": DocGenerationRouteStrategy(),
}

# 意图 → LangGraph 节点名
INTENT_TO_NODE: dict[str, str] = {
    intent: strategy.node_name for intent, strategy in _STRATEGIES.items()
}

DEFAULT_INTENT = "general_qa"


class UnknownIntentError(Exception):
    """未知意图。"""

    def __init__(self, intent: str) -> None:
        self.intent = intent
        super().__init__(f"未知意图: {intent}")


def get_route_strategy(intent: str) -> IntentRouteStrategy:
    """按意图返回路由策略实例。

    Args:
        intent: 意图识别结果，如 knowledge_query / general_qa / code_request / doc_generation。

    Returns:
        对应的策略实现；未知意图时回退到 general_qa。
    """
    strategy = _STRATEGIES.get(intent)
    if strategy is None:
        return _STRATEGIES[DEFAULT_INTENT]
    return strategy


def resolve_node_name(intent: str) -> str:
    """将意图映射为 LangGraph 节点名。"""
    return INTENT_TO_NODE.get(intent, INTENT_TO_NODE[DEFAULT_INTENT])
