"""发起对话业务逻辑。"""

from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, ConflictError, NotFoundError
from app.models.base_models import ConversationMode
from app.repositories.cache_repo import (
    CONVERSATION_CONTEXT_RECENT_KEEP,
    CONVERSATION_CONTEXT_SUMMARY_THRESHOLD,
    cache_repo,
)
from app.repositories.conversation_repo import conversation_repo
from app.repositories.message_repo import _message_to_dict, message_repo
from app.schemas.message import ChatRequest, ChatResponseData
from app.services.ai.conversation_summary import summarize_messages
from app.services.ai.llm_client import llm_client


def _build_conversation_title(content: str) -> str:
    """根据用户首条消息生成会话标题。"""
    normalized = content.strip()
    return normalized[:20] if normalized else "新对话"


def _content_type_to_mode(content_type: str) -> ConversationMode:
    """将消息内容类型映射为会话模式。"""
    if content_type == "code":
        return ConversationMode.code
    return ConversationMode.qa


class ChatService:
    """发起对话：加锁、存消息、构建上下文、调模型、更新会话。"""

    async def _ensure_conversation(
        self,
        db: AsyncSession,
        *,
        conversation_id: int | None,
        user_id: int,
        team_id: int,
        content: str,
        content_type: str,
    ):
        """获取或创建会话。"""
        if conversation_id is None:
            conversation = await conversation_repo.create(
                db,
                title=_build_conversation_title(content),
                mode=_content_type_to_mode(content_type),
                user_id=user_id,
                team_id=team_id,
            )
            await db.flush()
            return conversation

        conversation = await conversation_repo.get_by_id(
            db,
            conversation_id,
            user_id=user_id,
            team_id=team_id,
        )
        if not conversation:
            raise NotFoundError("对话不存在")
        return conversation

    async def _load_context(
        self,
        db: AsyncSession,
        redis: Redis,
        *,
        conversation_id: int,
        user_id: int,
        team_id: int,
    ) -> list[dict[str, Any]]:
        """优先从 Redis 获取上下文，未命中时回源数据库。"""
        cached = await cache_repo.get_conversation_messages(redis, conversation_id)
        if cached is not None:
            return cached

        rows = await message_repo.list_all(
            db,
            conversation_id=conversation_id,
            user_id=user_id,
            team_id=team_id,
        )
        if rows:
            await cache_repo.set_conversation_messages(redis, conversation_id, rows)
        return rows

    async def _build_system_prompt(
        self, context: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """上下文过长时生成摘要并保留最近消息。"""
        if len(context) <= CONVERSATION_CONTEXT_SUMMARY_THRESHOLD:
            return None, context

        older_messages = context[:-CONVERSATION_CONTEXT_RECENT_KEEP]
        recent_messages = context[-CONVERSATION_CONTEXT_RECENT_KEEP:]
        summary = await summarize_messages(older_messages)
        if not summary:
            return None, context

        system_prompt = f"以下是此前对话的摘要，供你参考：\n{summary}"
        return system_prompt, recent_messages

    async def send_message(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        payload: ChatRequest,
        redis: Redis | None,
    ) -> ChatResponseData:
        """发起一次对话并返回用户消息与助手回复。"""
        # 前置校验：本接口依赖 Redis 做分布式锁与消息缓存
        if redis is None:
            raise AppException(
                code=50301,
                message="服务暂不可用，请稍后重试",
                status_code=503,
            )

        user_id = int(user["id"])
        team_id = int(user["team_id"])

        # 步骤 7（前置）：首次对话无 conversation_id 时，先创建会话记录
        # 标题默认取用户消息前 20 字，模式由 content_type 映射（text→qa，code→code）
        conversation = await self._ensure_conversation(
            db,
            conversation_id=payload.conversation_id,
            user_id=user_id,
            team_id=team_id,
            content=payload.content,
            content_type=payload.content_type.value,
        )
        conversation_id = conversation.id

        # 步骤 1：获取分布式锁 conv:lock:{conversation_id}（SETNX，TTL 30s）
        # 同一对话并发发送时，后到的请求直接返回 409
        lock_acquired = await cache_repo.acquire_conversation_lock(
            redis, conversation_id
        )
        if not lock_acquired:
            raise ConflictError("消息处理中")

        try:
            # 步骤 2：将用户提问写入数据库（role=user，含 content / content_type）
            user_message = await message_repo.save_message(
                db,
                conversation_id,
                "user",
                payload.content,
                payload.content_type.value,
            )
            user_msg_data = _message_to_dict(user_message)

            # 步骤 3：将用户消息追加到 Redis 列表 conv:msg:{conversation_id}
            # 缓存未命中时从数据库回源全量历史，再写入缓存并刷新 TTL（15 分钟）
            cached = await cache_repo.get_conversation_messages(redis, conversation_id)
            if cached is None:
                context = await message_repo.list_all(
                    db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    team_id=team_id,
                )
            else:
                context = cached
                if not context or context[-1].get("id") != user_message.id:
                    context = [*context, user_msg_data]
            await cache_repo.set_conversation_messages(redis, conversation_id, context)

            # 步骤 4：构建 LLM 上下文
            # 消息总数超过 20 条时，对较早历史做摘要并注入 system 提示词，仅保留最近 10 条完整消息
            system_prompt, llm_context = await self._build_system_prompt(context)

            # 调用大模型生成助手回复
            assistant_content = await llm_client.chat(
                llm_context,
                system_prompt=system_prompt,
            )

            # 步骤 5：将助手回复写入数据库，并同步追加到 Redis 消息列表
            assistant_message = await message_repo.save_message(
                db,
                conversation_id,
                "assistant",
                assistant_content,
                payload.content_type.value,
            )
            assistant_msg_data = _message_to_dict(assistant_message)
            context = [*context, assistant_msg_data]
            await cache_repo.set_conversation_messages(redis, conversation_id, context)

            # 步骤 6：刷新会话 updated_at，保证对话列表按最近活跃时间排序
            await conversation_repo.touch_updated_at(db, conversation_id)
            await db.commit()

            # commit 后再次 refresh，确保返回给前端的时间戳等字段完整
            await db.refresh(user_message)
            await db.refresh(assistant_message)

            return ChatResponseData(
                user_msg=_message_to_dict(user_message),
                assistant_msg=_message_to_dict(assistant_message),
            )
        except Exception:
            await db.rollback()
            raise
        finally:
            # 步骤 8：无论成功或失败，都释放分布式锁
            await cache_repo.release_conversation_lock(redis, conversation_id)


chat_service = ChatService()
