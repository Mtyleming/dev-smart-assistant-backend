"""知识库数据访问。"""

from sqlalchemy.ext.asyncio import AsyncSession


class KnowledgeRepository:
    """知识库表 CRUD 封装（骨架占位）。"""

    async def list_by_team(self, db: AsyncSession, team_id: str) -> list:
        """列出团队下的知识库。"""
        _ = (db, team_id)
        return []


knowledge_repo = KnowledgeRepository()
