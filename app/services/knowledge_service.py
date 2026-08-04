"""知识库业务逻辑。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.base_models import KnowledgeBase
from app.repositories.knowledge_repo import knowledge_repo
from app.repositories.vector_repo import vector_repo
from app.schemas.knowledge import (
    KnowledgeCreateData,
    KnowledgeCreateRequest,
    KnowledgeIdRequest,
    KnowledgeItem,
    KnowledgePageData,
    KnowledgePageRequest,
    KnowledgeUpdateRequest,
)


def _to_item(kb: KnowledgeBase) -> KnowledgeItem:
    return KnowledgeItem(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        team_id=kb.team_id,
        created_by=kb.created_by,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


class KnowledgeService:
    """知识库管理业务。"""

    @staticmethod
    def _team_id(user: dict[str, Any]) -> int:
        return int(user["team_id"])

    @staticmethod
    def _user_id(user: dict[str, Any]) -> int:
        return int(user["id"])

    async def create(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeCreateRequest,
    ) -> KnowledgeCreateData:
        team_id = self._team_id(user)
        name = body.name.strip()
        exists = await knowledge_repo.get_by_team_and_name(db, team_id, name)
        if exists:
            raise ConflictError("知识库名称已存在")

        kb = await knowledge_repo.create(
            db,
            name=name,
            description=body.description,
            team_id=team_id,
            created_by=self._user_id(user),
        )
        await db.commit()
        return KnowledgeCreateData(id=kb.id)

    async def page(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgePageRequest,
    ) -> KnowledgePageData:
        team_id = self._team_id(user)
        keyword = body.keyword.strip() if body.keyword else None
        items, total = await knowledge_repo.page_by_team(
            db,
            team_id,
            page=body.page,
            page_size=body.page_size,
            keyword=keyword or None,
        )
        return KnowledgePageData(
            items=[_to_item(kb) for kb in items],
            total=total,
            page=body.page,
        )

    async def get_by_id(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeIdRequest,
    ) -> KnowledgeItem:
        kb = await knowledge_repo.get_by_id_and_team(
            db, body.id, self._team_id(user)
        )
        if not kb:
            raise NotFoundError("知识库不存在")
        return _to_item(kb)

    async def update(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeUpdateRequest,
    ) -> None:
        team_id = self._team_id(user)
        kb = await knowledge_repo.get_by_id_and_team(db, body.id, team_id)
        if not kb:
            raise NotFoundError("知识库不存在")

        fields = body.model_fields_set
        new_name = None
        if "name" in fields:
            new_name = body.name.strip() if body.name else body.name
            dup = await knowledge_repo.get_by_team_and_name(
                db, team_id, new_name, exclude_id=kb.id
            )
            if dup:
                raise ConflictError("知识库名称已存在")

        set_description = "description" in fields
        await knowledge_repo.update(
            db,
            kb,
            name=new_name,
            description=body.description if set_description else None,
            set_description=set_description,
        )
        await db.commit()

    async def delete(
        self,
        db: AsyncSession,
        user: dict[str, Any],
        body: KnowledgeIdRequest,
    ) -> None:
        team_id = self._team_id(user)
        kb = await knowledge_repo.get_by_id_and_team(db, body.id, team_id)
        if not kb:
            raise NotFoundError("知识库不存在")

        # 先清向量；失败则抛错，不执行下方 delete / commit
        await vector_repo.delete_by_knowledge_base(team_id, kb.id)
        await knowledge_repo.delete(db, kb)
        await db.commit()

    async def list_knowledge_bases(
        self,
        db: AsyncSession,
        user: dict[str, Any],
    ) -> list:
        """兼容旧调用。"""
        items, _ = await knowledge_repo.page_by_team(
            db, self._team_id(user), page=1, page_size=1000
        )
        return [_to_item(kb) for kb in items]


knowledge_service = KnowledgeService()
