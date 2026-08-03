"""LangGraph 多步骤 Agent 状态机封装（骨架占位）。"""

from app.services.ai.conversation_summary import DEFAULT_AGENT_TOOLS


class AgentGraph:
    """意图识别 → 路由分发 → 执行 → 汇总。"""

    def __init__(self, tools: list | None = None) -> None:
        self.tools = tools if tools is not None else DEFAULT_AGENT_TOOLS

    async def run(self, question: str, context: dict | None = None) -> dict:
        """运行一次 Agent 工作流，返回纯数据结果。"""
        _ = (context, self.tools)
        return {
            "answer": f"（骨架占位）Agent 尚未接入：{question}",
            "steps": [],
        }


agent_graph = AgentGraph()
