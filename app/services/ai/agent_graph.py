"""LangGraph 多步骤 Agent 状态机封装（骨架占位）。"""


class AgentGraph:
    """意图识别 → 路由分发 → 执行 → 汇总。"""

    async def run(self, question: str, context: dict | None = None) -> dict:
        """运行一次 Agent 工作流，返回纯数据结果。"""
        _ = context
        return {
            "answer": f"（骨架占位）Agent 尚未接入：{question}",
            "steps": [],
        }


agent_graph = AgentGraph()
