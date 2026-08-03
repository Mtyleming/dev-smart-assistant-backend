"""消息业务逻辑。"""

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.cache_repo import (
    CONVERSATION_MESSAGES_TTL_SECONDS,
    cache_repo,
)
from app.repositories.conversation_repo import conversation_repo
from app.repositories.message_repo import message_repo
from app.schemas.message import (
    MessageListData,
    MessageListItem,
    MessageListRequest,
    MessageRemoveRequest,
)


class MessageService:
    """消息查询与删除。"""

    async def invalidate_messages_cache(
        self,
        redis: Redis | None,
        conversation_id: int,
    ) -> None:
        """删除对话消息列表缓存。"""
        if redis is None:
            return
        await cache_repo.delete_conversation_messages(redis, conversation_id)

    async def _load_all_messages(
        self,
        db: AsyncSession,
        *,
        conversation_id: int,
        user_id: int,
        team_id: int,
        redis: Redis | None,
    ) -> list[dict]:
        """优先读 Redis 缓存，未命中时查库并回填缓存。"""
        if redis is not None:
            cached = await cache_repo.get_conversation_messages(redis, conversation_id)
            if cached is not None:
                await cache_repo.refresh_conversation_messages_ttl(
                    redis,
                    conversation_id,
                    CONVERSATION_MESSAGES_TTL_SECONDS,
                )
                return cached

        rows = await message_repo.list_all(
            db,
            conversation_id=conversation_id,
            user_id=user_id,
            team_id=team_id,
        )
        if redis is not None:
            await cache_repo.set_conversation_messages(
                redis,
                conversation_id,
                rows,
                CONVERSATION_MESSAGES_TTL_SECONDS,
            )
        return rows

    @staticmethod
    def _paginate(
        messages: list[dict],
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        """对消息列表做内存分页。"""
        total = len(messages)
        start = (page - 1) * page_size
        end = start + page_size
        return messages[start:end], total

    async def get_message_list(
        self,
        db: AsyncSession,
        user_id: str,
        team_id: str,
        payload: MessageListRequest,
        redis: Redis | None = None,
    ) -> MessageListData:
        """分页获取历史消息，优先从 Redis 读取。"""
        conversation = await conversation_repo.get_by_id(
            db,
            payload.conversation_id,
            user_id=int(user_id),
            team_id=int(team_id),
        )
        if not conversation:
            raise NotFoundError("对话不存在")

        all_messages = await self._load_all_messages(
            db,
            conversation_id=payload.conversation_id,
            user_id=int(user_id),
            team_id=int(team_id),
            redis=redis,
        )
        page_rows, total = self._paginate(
            all_messages,
            page=payload.page,
            page_size=payload.page_size,
        )
        items = [MessageListItem(**row) for row in page_rows]
        return MessageListData(items=items, total=total, page=payload.page)

    async def remove_message(
        self,
        db: AsyncSession,
        user_id: str,
        team_id: str,
        payload: MessageRemoveRequest,
        redis: Redis | None = None,
    ) -> None:
        """逻辑删除单条消息。"""
        message = await message_repo.get_by_id(
            db,
            payload.message_id,
            conversation_id=payload.conversation_id,
            user_id=int(user_id),
            team_id=int(team_id),
        )
        if not message:
            raise NotFoundError("消息不存在")

        await message_repo.soft_delete(db, message)
        await db.commit()
        await self.invalidate_messages_cache(redis, payload.conversation_id)


message_service = MessageService()
