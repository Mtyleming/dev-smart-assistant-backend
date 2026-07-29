"""RAG 检索链路封装（骨架占位）。"""

from app.repositories.vector_repo import vector_repo
from app.services.ai.llm_client import llm_client


class RAGPipeline:
    """向量检索 → 上下文组装 → 回答生成。"""

    async def query(
        self,
        question: str,
        team_id: str,
        kb_ids: list[str],
    ) -> dict:
        """执行 RAG 并返回回答与来源引用。"""
        chunks = await vector_repo.search(question, team_id, kb_ids)
        answer = await llm_client.generate(question, chunks)
        return {"answer": answer["text"], "sources": answer["sources"]}


rag_pipeline = RAGPipeline()
