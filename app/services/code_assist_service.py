"""代码辅助业务逻辑。"""

from app.services.ai.agent_graph import agent_graph


class CodeAssistService:
    """代码解释、生成、审查等能力的业务入口。"""

    async def assist(self, question: str, language: str | None = None) -> dict:
        """调用 Agent 处理代码相关问题。"""
        return await agent_graph.run(
            question=question,
            context={"language": language} if language else None,
        )


code_assist_service = CodeAssistService()
