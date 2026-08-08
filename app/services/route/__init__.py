"""意图路由：按意图选用不同策略（策略模式）。

四个意图与 LangGraph 四个节点对应：
- knowledge_query → rag
- general_qa → general
- code_request → code
- doc_generation → doc
"""

from app.services.route.base import IntentRouteStrategy
from app.services.route.factory import get_route_strategy, resolve_node_name

__all__ = [
    "IntentRouteStrategy",
    "get_route_strategy",
    "resolve_node_name",
]
