"""知识库业务逻辑。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.knowledge_repo import knowledge_repo


class KnowledgeService:
    """知识库管理业务。"""

    async def list_knowledge_bases(
        self,
        db: AsyncSession,
        user: dict[str, Any],
    ) -> list:
        """列出当前用户团队下的知识库。"""
        return await knowledge_repo.list_by_team(db, user["team_id"])


knowledge_service = KnowledgeService()
