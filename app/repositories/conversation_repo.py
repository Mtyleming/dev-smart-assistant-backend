"""对话与消息数据访问。"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import Conversation, ConversationMode
from app.repositories.sql import (
    LIST_CONVERSATION_PAGINATION_SQL,
    LIST_MINE_DATA_SQL,
    LIST_TEAM_DATA_SQL,
    wrap_count_sql,
)


def _row_to_conversation(row: Mapping[str, Any]) -> Conversation:
    """将查询行映射为 Conversation 对象。"""
    return Conversation(
        id=row["id"],
        title=row["title"],
        mode=ConversationMode(row["mode"]),
        user_id=row["user_id"],
        team_id=row["team_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        is_delete=bool(row["is_delete"]),
    )


def _list_params(
    *,
    team_id: int,
    page: int,
    page_size: int,
    title: str | None,
    mode: ConversationMode | None,
) -> dict[str, Any]:
    """普通成员 / 管理员共用的筛选参数。"""
    return {
        "team_id": team_id,
        "title": f"%{title}%" if title else None,
        "mode": mode.value if mode else None,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }


async def _query_paginated(
    db: AsyncSession,
    *,
    data_sql: str,
    params: dict[str, Any],
    with_creator: bool,
) -> tuple[list[tuple[Conversation, str | None]], int]:
    """执行分页查询并返回对话列表与总数。"""
    count_result = await db.execute(text(wrap_count_sql(data_sql)), params)
    total = int(count_result.scalar_one())

    data_result = await db.execute(
        text(f"{data_sql}{LIST_CONVERSATION_PAGINATION_SQL}"),
        params,
    )
    rows = [
        (
            _row_to_conversation(row),
            row.get("username") if with_creator else None,
        )
        for row in data_result.mappings().all()
    ]
    return rows, total


class ConversationRepository:
    """对话表 CRUD 封装。"""

    async def create(
        self,
        db: AsyncSession,
        *,
        title: str,
        mode: ConversationMode,
        user_id: int,
        team_id: int,
    ) -> Conversation:
        """创建对话记录。"""
        conversation = Conversation(
            title=title,
            mode=mode,
            user_id=user_id,
            team_id=team_id,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def get_by_id(
        self,
        db: AsyncSession,
        conversation_id: int,
        *,
        user_id: int,
        team_id: int,
    ) -> Conversation | None:
        """按 ID 查询当前用户在某团队下未删除的对话。"""
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.team_id == team_id,
                Conversation.is_delete.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        team_scope: bool,
        team_id: int,
        page: int,
        page_size: int,
        user_id: int | None = None,
        title: str | None = None,
        mode: ConversationMode | None = None,
        username: str | None = None,
    ) -> tuple[list[tuple[Conversation, str | None]], int]:
        """分页列出对话；team_scope=False 查本人，team_scope=True 查团队全部。"""
        params = _list_params(
            team_id=team_id,
            page=page,
            page_size=page_size,
            title=title,
            mode=mode,
        )
        if team_scope:
            params["username"] = f"%{username}%" if username else None
            data_sql = LIST_TEAM_DATA_SQL
        else:
            params["user_id"] = user_id
            data_sql = LIST_MINE_DATA_SQL

        return await _query_paginated(
            db,
            data_sql=data_sql,
            params=params,
            with_creator=team_scope,
        )

    async def update_title(
        self,
        db: AsyncSession,
        conversation: Conversation,
        title: str,
    ) -> Conversation:
        """更新对话标题。"""
        conversation.title = title
        await db.flush()
        return conversation

    async def soft_delete(
        self,
        db: AsyncSession,
        conversation: Conversation,
    ) -> None:
        """逻辑删除对话。"""
        conversation.is_delete = True
        await db.flush()


conversation_repo = ConversationRepository()
