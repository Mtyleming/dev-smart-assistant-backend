"""消息数据访问。"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import Message, MessageContentType, MessageRole
from app.repositories.sql import (
    LIST_MESSAGES_DATA_SQL,
    LIST_MESSAGES_PAGINATION_SQL,
    wrap_count_sql,
)


def _normalize_sources(raw: Any) -> list[dict[str, Any]] | None:
    """将 DB / ORM 中的 sources 规范为 list 或 None。"""
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        import json

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _row_to_message_item(row: Mapping[str, Any]) -> dict[str, Any]:
    """将查询行映射为消息列表项。"""
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "content_type": row.get("content_type") or MessageContentType.text.value,
        "sources": _normalize_sources(row.get("sources")),
        "created_at": row["created_at"],
    }


def _message_to_dict(message: Message) -> dict[str, Any]:
    """将 Message ORM 对象映射为字典。"""
    return {
        "id": message.id,
        "role": message.role.value,
        "content": message.content,
        "content_type": message.content_type.value,
        "sources": _normalize_sources(message.sources),
        "created_at": message.created_at,
    }


class MessageRepository:
    """消息表 CRUD 封装。"""

    async def save_message(
        self,
        db: AsyncSession,
        conversation_id: int,
        role: str,
        content: str,
        content_type: str = MessageContentType.text.value,
        *,
        sources: list[dict[str, Any]] | None = None,
    ) -> Message:
        """保存一条消息。"""
        message = Message(
            conversation_id=conversation_id,
            role=MessageRole(role),
            content=content,
            content_type=MessageContentType(content_type),
            sources=sources,
        )
        db.add(message)
        await db.flush()
        # flush 后需 refresh，否则 server_default 字段（如 created_at）会触发异步懒加载报错
        await db.refresh(message)
        return message

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        conversation_id: int,
        user_id: int,
        team_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页列出某对话下的消息，按创建时间正序。"""
        params = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "team_id": team_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }

        count_result = await db.execute(
            text(wrap_count_sql(LIST_MESSAGES_DATA_SQL)),
            params,
        )
        total = int(count_result.scalar_one())

        data_result = await db.execute(
            text(f"{LIST_MESSAGES_DATA_SQL}{LIST_MESSAGES_PAGINATION_SQL}"),
            params,
        )
        items = [
            _row_to_message_item(row)
            for row in data_result.mappings().all()
        ]
        return items, total

    async def list_all(
        self,
        db: AsyncSession,
        *,
        conversation_id: int,
        user_id: int,
        team_id: int,
    ) -> list[dict[str, Any]]:
        """列出某对话下的全部消息，按创建时间正序。"""
        params = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "team_id": team_id,
        }
        data_result = await db.execute(
            text(f"{LIST_MESSAGES_DATA_SQL}\nORDER BY m.created_at ASC"),
            params,
        )
        return [
            _row_to_message_item(row)
            for row in data_result.mappings().all()
        ]

    async def get_by_id(
        self,
        db: AsyncSession,
        message_id: int,
        *,
        conversation_id: int,
        user_id: int,
        team_id: int,
    ) -> Message | None:
        """按 ID 查询当前用户对话下未删除的消息。"""
        result = await db.execute(
            select(Message)
            .join(Message.conversation)
            .where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
                Message.is_delete.is_(False),
                Message.conversation.has(
                    user_id=user_id,
                    team_id=team_id,
                    is_delete=False,
                ),
            )
        )
        return result.scalar_one_or_none()

    async def soft_delete(
        self,
        db: AsyncSession,
        message: Message,
    ) -> None:
        """逻辑删除消息。"""
        message.is_delete = True
        await db.flush()


message_repo = MessageRepository()
