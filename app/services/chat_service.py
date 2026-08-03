"""智能问答业务逻辑。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.message_repo import message_repo
from app.services.ai.rag_pipeline import rag_pipeline


class ChatService:
    """对话问答：写消息 + 调 AI + 存回答。"""

    async def ask(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        question: str,
        conversation_id: int,
    ) -> dict:
        """处理一次问答请求。"""
        await message_repo.save_message(db, conversation_id, "user", question)
        result = await rag_pipeline.query(
            question=question,
            team_id=user["team_id"],
            kb_ids=user.get("accessible_kb_ids", []),
        )
        await message_repo.save_message(
            db, conversation_id, "assistant", result["answer"]
        )
        return result


chat_service = ChatService()
