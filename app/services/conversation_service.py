"""对话业务逻辑。"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.base_models import Conversation, ConversationMode
from app.repositories.conversation_repo import conversation_repo
from app.schemas.conversation import (
    ConversationBriefData,
    ConversationDetailData,
    ConversationListData,
    ConversationListItem,
    ConversationListScope,
    ConversationUpdateTitleRequest,
)

DEFAULT_CONVERSATION_TITLE = "新对话"


def _to_list_item(
    conversation: Conversation,
    creator_username: str | None,
    *,
    include_creator: bool,
) -> ConversationListItem:
    """将对话记录映射为列表项。"""
    return ConversationListItem(
        id=conversation.id,
        title=conversation.title,
        mode=conversation.mode.value,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        user_id=conversation.user_id if include_creator else None,
        username=creator_username if include_creator else None,
    )


class ConversationService:
    """对话增删改查。"""

    async def create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        team_id: str,
        mode: ConversationMode,
    ) -> ConversationBriefData:
        """创建对话，默认标题为「新对话」。"""
        conversation = await conversation_repo.create(
            db,
            title=DEFAULT_CONVERSATION_TITLE,
            mode=mode,
            user_id=int(user_id),
            team_id=int(team_id),
        )
        await db.commit()
        await db.refresh(conversation)
        return ConversationBriefData(
            id=conversation.id,
            title=conversation.title,
            mode=conversation.mode.value,
        )

    async def list_conversations(
        self,
        db: AsyncSession,
        user: dict,
        *,
        page: int,
        page_size: int,
        title: str | None = None,
        mode: ConversationMode | None = None,
        scope: ConversationListScope = ConversationListScope.mine,
        username: str | None = None,
    ) -> ConversationListData:
        """分页获取对话列表；admin 可通过 scope=team 查看当前团队全部对话。"""
        team_id = int(user["team_id"])
        is_team_scope = scope == ConversationListScope.team

        if is_team_scope and user["role"] != "admin":
            raise ForbiddenError("仅团队管理员可查看团队对话")

        rows, total = await conversation_repo.list_paginated(
            db,
            team_scope=is_team_scope,
            team_id=team_id,
            user_id=int(user["id"]),
            page=page,
            page_size=page_size,
            title=title,
            mode=mode,
            username=username,
        )

        items = [
            _to_list_item(
                conversation,
                creator_username,
                include_creator=is_team_scope,
            )
            for conversation, creator_username in rows
        ]
        return ConversationListData(items=items, total=total, page=page)

    async def get_conversation(
        self,
        db: AsyncSession,
        conversation_id: int,
        user_id: str,
        team_id: str,
    ) -> ConversationDetailData:
        """获取单个对话详情。"""
        conversation = await conversation_repo.get_by_id(
            db,
            conversation_id,
            user_id=int(user_id),
            team_id=int(team_id),
        )
        if not conversation:
            raise NotFoundError("对话不存在")

        return ConversationDetailData(
            id=conversation.id,
            title=conversation.title,
            mode=conversation.mode.value,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    async def update_title(
        self,
        db: AsyncSession,
        conversation_id: int,
        user_id: str,
        team_id: str,
        payload: ConversationUpdateTitleRequest,
    ) -> None:
        """修改对话标题。"""
        conversation = await conversation_repo.get_by_id(
            db,
            conversation_id,
            user_id=int(user_id),
            team_id=int(team_id),
        )
        if not conversation:
            raise NotFoundError("对话不存在")

        await conversation_repo.update_title(db, conversation, payload.title)
        await db.commit()

    async def delete_conversation(
        self,
        db: AsyncSession,
        conversation_id: int,
        user_id: str,
        team_id: str,
    ) -> None:
        """逻辑删除对话。"""
        conversation = await conversation_repo.get_by_id(
            db,
            conversation_id,
            user_id=int(user_id),
            team_id=int(team_id),
        )
        if not conversation:
            raise NotFoundError("对话不存在")

        await conversation_repo.soft_delete(db, conversation)
        await db.commit()


conversation_service = ConversationService()
