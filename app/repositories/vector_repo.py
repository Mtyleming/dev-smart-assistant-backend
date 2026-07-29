"""Milvus 向量检索封装（骨架占位）。"""


class VectorRepository:
    """向量库操作：检索相关文档切块。"""

    async def search(
        self,
        question: str,
        team_id: str,
        kb_ids: list[str],
    ) -> list[dict]:
        """按问题与知识库范围检索切块。"""
        _ = (question, team_id, kb_ids)
        return []


vector_repo = VectorRepository()
