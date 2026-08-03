"""对话消息数据访问。"""

from sqlalchemy.ext.asyncio import AsyncSession


class MessageRepository:
    """消息表 CRUD 封装（消息表待接入）。"""

    async def save_message(
        self,
        db: AsyncSession,
        conversation_id: int,
        role: str,
        content: str,
    ) -> None:
        """保存一条消息。"""
        _ = (db, conversation_id, role, content)
        return None

    async def list_messages(
        self,
        db: AsyncSession,
        conversation_id: int,
        team_id: int,
    ) -> list:
        """列出某对话的消息。"""
        _ = (db, conversation_id, team_id)
        return []


message_repo = MessageRepository()
