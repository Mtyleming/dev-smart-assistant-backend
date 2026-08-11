"""发起对话业务逻辑。"""

from collections.abc import AsyncIterator
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
from app.services.ai.citation_verifier import verify_and_filter_citations
from app.services.ai.conversation_summary import summarize_messages
from app.services.ai.intent_service import classify_intent
from app.services.ai.llm_client import GENERAL_FALLBACK_SYSTEM_PROMPT, llm_client
from app.services.ai.rag_pipeline import (
    _CONFIRM_HINT,
    build_rag_system_prompt,
    rag_pipeline,
    take_recent_turns,
)
from app.services.route import get_route_strategy

# 代码解读非流式结果按块模拟 SSE delta，避免一次塞整篇 Markdown
_CODE_ANSWER_CHUNK_SIZE = 80


def _chunk_text(text: str, size: int = _CODE_ANSWER_CHUNK_SIZE) -> list[str]:
    """将文本按固定长度切分，供 SSE 逐块推送。"""
    if not text:
        return []
    if size <= 0:
        return [text]
    return [text[i : i + size] for i in range(0, len(text), size)]


def _build_conversation_title(content: str) -> str:
    """根据用户首条消息生成会话标题。"""
    normalized = content.strip()
    return normalized[:20] if normalized else "新对话"


def _content_type_to_mode(content_type: str) -> ConversationMode:
    """将消息内容类型映射为会话模式。"""
    if content_type == "code":
        return ConversationMode.code
    return ConversationMode.qa


def _kb_ids_from_payload(payload: ChatRequest) -> list[int]:
    """从请求解析知识库过滤列表；空表示团队全部知识库。"""
    if payload.knowledge_base_id is None:
        return []
    return [int(payload.knowledge_base_id)]


class ChatService:
    """发起对话：加锁、存消息、意图路由、RAG/通用生成、更新会话。"""

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
        """上下文过长时生成摘要并保留最近消息（通用问答路径）。"""
        if len(context) <= CONVERSATION_CONTEXT_SUMMARY_THRESHOLD:
            return None, context

        older_messages = context[:-CONVERSATION_CONTEXT_RECENT_KEEP]
        recent_messages = context[-CONVERSATION_CONTEXT_RECENT_KEEP:]
        summary = await summarize_messages(older_messages)
        if not summary:
            return None, context

        system_prompt = f"以下是此前对话的摘要，供你参考：\n{summary}"
        return system_prompt, recent_messages

    async def _prepare_context_after_user_msg(
        self,
        db: AsyncSession,
        redis: Redis,
        *,
        conversation_id: int,
        user_id: int,
        team_id: int,
        user_message,
        user_msg_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """用户消息入库后刷新 Redis 上下文并返回完整上下文。"""
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
        return context

    async def _generate_assistant_reply(
        self,
        *,
        redis: Redis,
        team_id: int,
        conversation_id: int,
        question: str,
        context: list[dict[str, Any]],
        kb_ids: list[int],
        content_type: str | None = None,
    ) -> tuple[str, list[dict[str, Any]] | None, str]:
        """按意图生成助手回复。

        Returns:
            (answer_text, sources_or_none, intent)
        """
        intent_result = await classify_intent(
            question, conversation_id, redis
        )
        intent = str(intent_result.get("intent") or "general_qa")

        if intent == "knowledge_query":
            retrieved = await rag_pipeline.retrieve(
                question, team_id=team_id, kb_ids=kb_ids
            )
            if not retrieved["use_retrieval"]:
                answer = await llm_client.generate_general_fallback(question)
                return answer, [], intent

            system_prompt = build_rag_system_prompt(retrieved["context_text"])
            recent = take_recent_turns(context, max_turns=3)
            if (
                recent
                and recent[-1]["role"] == "user"
                and recent[-1]["content"] == question
            ):
                recent = recent[:-1]
                recent = take_recent_turns(recent, max_turns=3)

            messages = [*recent, {"role": "user", "content": question}]
            raw = await llm_client.chat(messages, system_prompt=system_prompt)
            answer, sources, _ = verify_and_filter_citations(
                raw, retrieved["chunks"]
            )
            if (
                retrieved["confidence"] == "medium"
                and _CONFIRM_HINT not in answer
            ):
                answer = f"{answer}\n\n{_CONFIRM_HINT}"
            return answer, sources, intent

        if intent == "code_request":
            strategy = get_route_strategy("code_request")
            result = await strategy.run(
                question,
                conversation_id,
                team_id=team_id,
                kb_ids=kb_ids,
                content_type=content_type,
            )
            answer = str(result.get("answer") or "").strip()
            sources = result.get("sources")
            if sources is None:
                sources = []
            return answer, sources, intent

        # 其它意图：沿用通用对话（含长上下文摘要）
        system_prompt, llm_context = await self._build_system_prompt(context)
        answer = await llm_client.chat(llm_context, system_prompt=system_prompt)
        return answer, None, intent

    async def _stream_assistant_reply(
        self,
        *,
        redis: Redis,
        team_id: int,
        conversation_id: int,
        question: str,
        context: list[dict[str, Any]],
        kb_ids: list[int],
        content_type: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """流式生成助手回复，产出 delta / 最终 (final, text, sources, intent)。"""
        intent_result = await classify_intent(
            question, conversation_id, redis
        )
        intent = str(intent_result.get("intent") or "general_qa")

        if intent == "knowledge_query":
            retrieved = await rag_pipeline.retrieve(
                question, team_id=team_id, kb_ids=kb_ids
            )
            if not retrieved["use_retrieval"]:
                chunks: list[str] = []
                async for piece in llm_client.chat_stream(
                    [{"role": "user", "content": question}],
                    system_prompt=GENERAL_FALLBACK_SYSTEM_PROMPT,
                ):
                    chunks.append(piece)
                    yield "delta", {"content": piece}
                text = "".join(chunks).strip()
                from app.services.ai.llm_client import _NOT_FOUND_HINT

                if _NOT_FOUND_HINT not in text:
                    text = f"{_NOT_FOUND_HINT}。\n\n{text}"
                yield "final", {
                    "content": text,
                    "sources": [],
                    "intent": intent,
                }
                return

            system_prompt = build_rag_system_prompt(retrieved["context_text"])
            recent = take_recent_turns(context, max_turns=3)
            if (
                recent
                and recent[-1]["role"] == "user"
                and recent[-1]["content"] == question
            ):
                recent = recent[:-1]
                recent = take_recent_turns(recent, max_turns=3)
            messages = [*recent, {"role": "user", "content": question}]

            pieces: list[str] = []
            async for piece in llm_client.chat_stream(
                messages, system_prompt=system_prompt
            ):
                pieces.append(piece)
                yield "delta", {"content": piece}

            raw = "".join(pieces).strip()
            answer, sources, _ = verify_and_filter_citations(
                raw, retrieved["chunks"]
            )
            if (
                retrieved["confidence"] == "medium"
                and _CONFIRM_HINT not in answer
            ):
                answer = f"{answer}\n\n{_CONFIRM_HINT}"
            # 若校验删改了正文，补发一次校正后的全文事件供前端对齐
            if answer != raw:
                yield "citation_verified", {
                    "content": answer,
                    "sources": sources,
                }
            yield "final", {
                "content": answer,
                "sources": sources,
                "intent": intent,
            }
            return

        if intent == "code_request":
            strategy = get_route_strategy("code_request")
            result = await strategy.run(
                question,
                conversation_id,
                team_id=team_id,
                kb_ids=kb_ids,
                content_type=content_type,
            )
            answer = str(result.get("answer") or "").strip()
            sources = result.get("sources")
            if sources is None:
                sources = []
            for piece in _chunk_text(answer):
                yield "delta", {"content": piece}
            yield "final", {
                "content": answer,
                "sources": sources,
                "intent": intent,
            }
            return

        system_prompt, llm_context = await self._build_system_prompt(context)
        pieces = []
        async for piece in llm_client.chat_stream(
            llm_context, system_prompt=system_prompt
        ):
            pieces.append(piece)
            yield "delta", {"content": piece}
        yield "final", {
            "content": "".join(pieces).strip(),
            "sources": None,
            "intent": intent,
        }

    async def send_message(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        payload: ChatRequest,
        redis: Redis | None,
    ) -> ChatResponseData:
        """发起一次对话并返回用户消息与助手回复。"""
        if redis is None:
            raise AppException(
                code=50301,
                message="服务暂不可用，请稍后重试",
                status_code=503,
            )

        user_id = int(user["id"])
        team_id = int(user["team_id"])
        kb_ids = _kb_ids_from_payload(payload)

        conversation = await self._ensure_conversation(
            db,
            conversation_id=payload.conversation_id,
            user_id=user_id,
            team_id=team_id,
            content=payload.content,
            content_type=payload.content_type.value,
        )
        conversation_id = conversation.id

        lock_acquired = await cache_repo.acquire_conversation_lock(
            redis, conversation_id
        )
        if not lock_acquired:
            raise ConflictError("消息处理中")

        try:
            user_message = await message_repo.save_message(
                db,
                conversation_id,
                "user",
                payload.content,
                payload.content_type.value,
            )
            user_msg_data = _message_to_dict(user_message)
            context = await self._prepare_context_after_user_msg(
                db,
                redis,
                conversation_id=conversation_id,
                user_id=user_id,
                team_id=team_id,
                user_message=user_message,
                user_msg_data=user_msg_data,
            )

            assistant_content, sources, _intent = await self._generate_assistant_reply(
                redis=redis,
                team_id=team_id,
                conversation_id=conversation_id,
                question=payload.content,
                context=context,
                kb_ids=kb_ids,
                content_type=payload.content_type.value,
            )

            assistant_message = await message_repo.save_message(
                db,
                conversation_id,
                "assistant",
                assistant_content,
                payload.content_type.value,
                sources=sources,
            )
            assistant_msg_data = _message_to_dict(assistant_message)
            context = [*context, assistant_msg_data]
            await cache_repo.set_conversation_messages(redis, conversation_id, context)

            await conversation_repo.touch_updated_at(db, conversation_id)
            await db.commit()

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
            await cache_repo.release_conversation_lock(redis, conversation_id)

    async def send_message_stream(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        payload: ChatRequest,
        redis: Redis | None,
    ) -> AsyncIterator[tuple[str | None, Any]]:
        """
        流式发起对话，按 SSE 事件逐步产出：
        - conversation / user_msg / delta / citation_verified / assistant_msg / done
        """
        if redis is None:
            raise AppException(
                code=50301,
                message="服务暂不可用，请稍后重试",
                status_code=503,
            )

        user_id = int(user["id"])
        team_id = int(user["team_id"])
        kb_ids = _kb_ids_from_payload(payload)

        conversation = await self._ensure_conversation(
            db,
            conversation_id=payload.conversation_id,
            user_id=user_id,
            team_id=team_id,
            content=payload.content,
            content_type=payload.content_type.value,
        )
        conversation_id = conversation.id

        if payload.conversation_id is None:
            yield "conversation", {"conversation_id": conversation_id}

        lock_acquired = await cache_repo.acquire_conversation_lock(
            redis, conversation_id
        )
        if not lock_acquired:
            raise ConflictError("消息处理中")

        try:
            user_message = await message_repo.save_message(
                db,
                conversation_id,
                "user",
                payload.content,
                payload.content_type.value,
            )
            user_msg_data = _message_to_dict(user_message)
            yield "user_msg", user_msg_data

            context = await self._prepare_context_after_user_msg(
                db,
                redis,
                conversation_id=conversation_id,
                user_id=user_id,
                team_id=team_id,
                user_message=user_message,
                user_msg_data=user_msg_data,
            )

            assistant_content = ""
            sources: list[dict[str, Any]] | None = None
            async for event_name, event_data in self._stream_assistant_reply(
                redis=redis,
                team_id=team_id,
                conversation_id=conversation_id,
                question=payload.content,
                context=context,
                kb_ids=kb_ids,
                content_type=payload.content_type.value,
            ):
                if event_name == "delta":
                    yield "delta", event_data
                elif event_name == "citation_verified":
                    yield "citation_verified", event_data
                elif event_name == "final":
                    assistant_content = str(event_data.get("content") or "")
                    sources = event_data.get("sources")

            assistant_message = await message_repo.save_message(
                db,
                conversation_id,
                "assistant",
                assistant_content,
                payload.content_type.value,
                sources=sources,
            )
            assistant_msg_data = _message_to_dict(assistant_message)
            context = [*context, assistant_msg_data]
            await cache_repo.set_conversation_messages(redis, conversation_id, context)

            await conversation_repo.touch_updated_at(db, conversation_id)
            await db.commit()

            await db.refresh(user_message)
            await db.refresh(assistant_message)

            yield "assistant_msg", _message_to_dict(assistant_message)
            yield "done", {"sources": sources or []}
        except Exception:
            await db.rollback()
            raise
        finally:
            await cache_repo.release_conversation_lock(redis, conversation_id)


chat_service = ChatService()
