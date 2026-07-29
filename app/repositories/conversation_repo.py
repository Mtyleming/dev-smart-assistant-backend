"""对话与消息数据访问。"""

from sqlalchemy.ext.asyncio import AsyncSession


class ConversationRepository:
    """对话/消息 CRUD 封装（骨架占位）。"""

    async def save_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        """保存一条消息。"""
        _ = (db, conversation_id, role, content)
        return None

    async def list_messages(
        self,
        db: AsyncSession,
        conversation_id: str,
        team_id: str,
    ) -> list:
        """列出某对话的消息。"""
        _ = (db, conversation_id, team_id)
        return []


conversation_repo = ConversationRepository()
