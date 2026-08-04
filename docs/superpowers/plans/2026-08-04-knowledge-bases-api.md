# 知识库管理接口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现知识库 CRUD 五个 POST 接口（创建/分页/详情/修改/删除），删除时先清 Milvus 再删 MySQL。

**Architecture:** 沿用路由 → 服务 → Repository。`team_id` 取自 Token 当前团队；写操作依赖 `admin`/`tech_lead`；`vector_repo` 按 `knowledge_base_id + team_id` 删除向量，失败则不删 MySQL。

**Tech Stack:** FastAPI、SQLAlchemy 2 异步、Pydantic v2、pymilvus、现有 `AppException` 体系

**Spec:** `docs/superpowers/specs/2026-08-04-knowledge-bases-api-design.md`

---

## File Structure

| 文件 | 职责 |
|------|------|
| `app/schemas/knowledge.py` | 请求/响应 DTO |
| `app/dependencies.py` | 增加 `CurrentTeamAdminOrLead` |
| `app/core/config.py` / `.env.example` | Milvus URI、collection 名 |
| `requirements.txt` | 增加 `pymilvus` |
| `app/repositories/knowledge_repo.py` | MySQL CRUD + 分页 + 重名查询 |
| `app/repositories/vector_repo.py` | Milvus 按知识库删除 |
| `app/services/knowledge_service.py` | 业务编排与异常 |
| `app/routers/knowledge_bases.py` | 五个 POST + `/status` |
| `app/main.py` | 挂载路由 |
| `README.md` | 接口说明与进度 |
| `test/test_knowledge_schemas.py` | Schema 校验单测（轻量） |

---

### Task 1: Milvus 配置与依赖

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/config.py`
- Modify: `.env.example`

- [ ] **Step 1: 在 `requirements.txt` 末尾增加 pymilvus**

```text
# 向量库
pymilvus>=2.4.0,<3.0.0
```

- [ ] **Step 2: 在 `app/core/config.py` 的 `Settings` 中增加字段（放在 `super_admin_user_id` 附近）**

```python
    # Milvus 连接地址（本地默认）
    milvus_uri: str = Field(
        default="http://127.0.0.1:19530",
        validation_alias=AliasChoices("MILVUS_URI"),
    )
    # 文档切块向量 Collection 名
    milvus_collection: str = Field(
        default="document_chunks",
        validation_alias=AliasChoices("MILVUS_COLLECTION"),
    )
```

- [ ] **Step 3: 在 `.env.example` 末尾增加**

```env
# Milvus（删除知识库时清理向量）
MILVUS_URI=http://127.0.0.1:19530
MILVUS_COLLECTION=document_chunks
```

- [ ] **Step 4: 安装依赖**

Run: `pip install "pymilvus>=2.4.0,<3.0.0"`

Expected: 安装成功，无报错

- [ ] **Step 5: 可选提交（仅当用户明确要求 commit 时执行）**

```bash
git add requirements.txt app/core/config.py .env.example
git commit -m "chore: add Milvus config for knowledge base deletion"
```

---

### Task 2: Schema 与权限依赖

**Files:**
- Create: `app/schemas/knowledge.py`
- Create: `test/test_knowledge_schemas.py`
- Modify: `app/dependencies.py`

- [ ] **Step 1: 新建 `app/schemas/knowledge.py`**

```python
"""知识库请求与响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeCreateRequest(BaseModel):
    """创建知识库。"""

    name: str = Field(..., min_length=1, max_length=200, description="知识库名称")
    description: str | None = Field(default=None, description="知识库描述")


class KnowledgePageRequest(BaseModel):
    """分页查询知识库。"""

    model_config = ConfigDict(populate_by_name=True)

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(
        default=20, ge=1, le=100, alias="pageSize", description="每页条数"
    )
    keyword: str | None = Field(default=None, description="按名称模糊搜索")


class KnowledgeIdRequest(BaseModel):
    """按 ID 操作（详情/删除）。"""

    id: int = Field(..., ge=1, description="知识库 ID")


class KnowledgeUpdateRequest(BaseModel):
    """修改知识库：至少提供 name 或 description 之一。"""

    id: int = Field(..., ge=1, description="知识库 ID")
    name: str | None = Field(default=None, min_length=1, max_length=200, description="新名称")
    description: str | None = Field(default=None, description="新描述，传 null 可清空")

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "KnowledgeUpdateRequest":
        # 用 fields_set 区分「未传 description」与「显式传 null」
        provided = self.model_fields_set - {"id"}
        if not provided:
            raise ValueError("至少需要提供 name 或 description 之一")
        if "name" in provided and self.name is None:
            raise ValueError("name 不能为空")
        return self


class KnowledgeItem(BaseModel):
    """知识库详情/列表项。"""

    id: int
    name: str
    description: str | None
    team_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime


class KnowledgeCreateData(BaseModel):
    """创建成功返回标识。"""

    id: int


class KnowledgePageData(BaseModel):
    """分页列表。"""

    items: list[KnowledgeItem]
    total: int
    page: int
```

- [ ] **Step 2: 新建 `test/test_knowledge_schemas.py`**

```python
"""知识库 Schema 校验。"""

import pytest
from pydantic import ValidationError

from app.schemas.knowledge import KnowledgeUpdateRequest


def test_update_requires_at_least_one_field():
    with pytest.raises(ValidationError):
        KnowledgeUpdateRequest(id=1)


def test_update_allows_description_null():
    body = KnowledgeUpdateRequest(id=1, description=None)
    assert "description" in body.model_fields_set
    assert body.description is None


def test_update_name_only():
    body = KnowledgeUpdateRequest(id=1, name="新名称")
    assert body.name == "新名称"
```

- [ ] **Step 3: 运行 Schema 单测**

Run: `pip install pytest -q && python -m pytest test/test_knowledge_schemas.py -v`

Expected: 3 passed

- [ ] **Step 4: 在 `app/dependencies.py` 中 `CurrentUser` 定义后增加**

```python
# Token 当前团队：admin 或 tech_lead
CurrentTeamAdminOrLead = Annotated[
    dict[str, Any],
    Depends(current_user("admin", "tech_lead")),
]
```

- [ ] **Step 5: 可选提交**

```bash
git add app/schemas/knowledge.py test/test_knowledge_schemas.py app/dependencies.py
git commit -m "feat: add knowledge schemas and admin/tech_lead dependency"
```

---

### Task 3: knowledge_repo 数据访问

**Files:**
- Modify: `app/repositories/knowledge_repo.py`

- [ ] **Step 1: 用以下完整实现替换 `app/repositories/knowledge_repo.py`**

```python
"""知识库数据访问。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import KnowledgeBase


class KnowledgeRepository:
    """知识库表 CRUD 封装。"""

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        description: str | None,
        team_id: int,
        created_by: int,
    ) -> KnowledgeBase:
        """创建知识库并 flush 拿到自增 ID。"""
        kb = KnowledgeBase(
            name=name,
            description=description,
            team_id=team_id,
            created_by=created_by,
        )
        db.add(kb)
        await db.flush()
        await db.refresh(kb)
        return kb

    async def get_by_id_and_team(
        self, db: AsyncSession, kb_id: int, team_id: int
    ) -> KnowledgeBase | None:
        """按 ID + 团队查询（跨团队视为不存在）。"""
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.team_id == team_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_team_and_name(
        self,
        db: AsyncSession,
        team_id: int,
        name: str,
        *,
        exclude_id: int | None = None,
    ) -> KnowledgeBase | None:
        """同团队按名称查重；exclude_id 用于更新时排除自身。"""
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.team_id == team_id,
            KnowledgeBase.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(KnowledgeBase.id != exclude_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def page_by_team(
        self,
        db: AsyncSession,
        team_id: int,
        *,
        page: int,
        page_size: int,
        keyword: str | None = None,
    ) -> tuple[list[KnowledgeBase], int]:
        """分页列出团队知识库，按 updated_at 降序。"""
        filters = [KnowledgeBase.team_id == team_id]
        if keyword:
            filters.append(KnowledgeBase.name.like(f"%{keyword}%"))

        count_result = await db.execute(
            select(func.count()).select_from(KnowledgeBase).where(*filters)
        )
        total = int(count_result.scalar_one())

        result = await db.execute(
            select(KnowledgeBase)
            .where(*filters)
            .order_by(KnowledgeBase.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        db: AsyncSession,
        kb: KnowledgeBase,
        *,
        name: str | None = None,
        description: str | None = None,
        set_description: bool = False,
    ) -> KnowledgeBase:
        """更新字段；set_description=True 时允许把 description 写成 None。"""
        if name is not None:
            kb.name = name
        if set_description:
            kb.description = description
        await db.flush()
        await db.refresh(kb)
        return kb

    async def delete(self, db: AsyncSession, kb: KnowledgeBase) -> None:
        """物理删除知识库记录。"""
        await db.delete(kb)
        await db.flush()

    async def list_by_team(self, db: AsyncSession, team_id: int) -> list[KnowledgeBase]:
        """列出团队下的知识库（保留给兼容调用）。"""
        items, _ = await self.page_by_team(db, team_id, page=1, page_size=1000)
        return items

    async def count_by_team(self, db: AsyncSession, team_id: int) -> int:
        """统计团队关联的知识库数量。"""
        result = await db.execute(
            select(func.count())
            .select_from(KnowledgeBase)
            .where(KnowledgeBase.team_id == team_id)
        )
        return int(result.scalar_one())


knowledge_repo = KnowledgeRepository()
```

注意：`team_service` 解散团队仍调用 `count_by_team`，必须保留。

- [ ] **Step 2: 确认语法**

Run: `python -c "from app.repositories.knowledge_repo import knowledge_repo; print('ok')"`

Expected: `ok`

- [ ] **Step 3: 可选提交**

```bash
git add app/repositories/knowledge_repo.py
git commit -m "feat: expand knowledge repository CRUD and pagination"
```

---

### Task 4: vector_repo 按知识库删除向量

**Files:**
- Modify: `app/repositories/vector_repo.py`

- [ ] **Step 1: 用以下实现替换 `app/repositories/vector_repo.py`**

```python
"""Milvus 向量检索与清理封装。"""

import asyncio
import logging

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class VectorRepository:
    """向量库操作：检索相关文档切块、按知识库清理。"""

    async def search(
        self,
        question: str,
        team_id: str,
        kb_ids: list[str],
    ) -> list[dict]:
        """按问题与知识库范围检索切块（占位，后续 RAG 接入）。"""
        _ = (question, team_id, kb_ids)
        return []

    async def delete_by_knowledge_base(self, team_id: int, knowledge_base_id: int) -> None:
        """
        删除某知识库在 Milvus 中的全部切块向量。

        过滤：knowledge_base_id == id AND team_id == team_id
        失败时抛出 AppException，调用方不得继续删 MySQL。
        """
        try:
            await asyncio.to_thread(
                self._delete_sync, int(team_id), int(knowledge_base_id)
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "Milvus 清理失败 team_id=%s kb_id=%s", team_id, knowledge_base_id
            )
            raise AppException(
                code=50301,
                message="向量数据清理失败，知识库未删除",
                status_code=503,
            ) from exc

    def _delete_sync(self, team_id: int, knowledge_base_id: int) -> None:
        """同步调用 pymilvus（在线程池中执行）。"""
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        collection = settings.milvus_collection
        expr = (
            f"knowledge_base_id == {knowledge_base_id} and team_id == {team_id}"
        )
        # 集合不存在时：视为无向量可清，直接成功（避免空环境删库被卡死）
        if not client.has_collection(collection_name=collection):
            logger.warning("Milvus collection 不存在，跳过清理: %s", collection)
            return
        client.delete(collection_name=collection, filter=expr)


vector_repo = VectorRepository()
```

说明：Collection 不存在时跳过清理并成功——本地未建 collection 时仍可删 MySQL；**真正连不上 Milvus**（连接异常）仍会失败并阻止删库，符合设计「A」。

- [ ] **Step 2: 语法检查**

Run: `python -c "from app.repositories.vector_repo import vector_repo; print('ok')"`

Expected: `ok`

- [ ] **Step 3: 可选提交**

```bash
git add app/repositories/vector_repo.py
git commit -m "feat: delete Milvus chunks by knowledge base id"
```

---

### Task 5: knowledge_service 业务层

**Files:**
- Modify: `app/services/knowledge_service.py`

- [ ] **Step 1: 用以下实现替换 `app/services/knowledge_service.py`**

```python
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
        exists = await knowledge_repo.get_by_team_and_name(db, team_id, body.name)
        if exists:
            raise ConflictError("知识库名称已存在")

        kb = await knowledge_repo.create(
            db,
            name=body.name.strip(),
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
```

- [ ] **Step 2: 导入检查**

Run: `python -c "from app.services.knowledge_service import knowledge_service; print('ok')"`

Expected: `ok`

- [ ] **Step 3: 可选提交**

```bash
git add app/services/knowledge_service.py
git commit -m "feat: implement knowledge base service CRUD with Milvus-aware delete"
```

---

### Task 6: 路由挂载

**Files:**
- Modify: `app/routers/knowledge_bases.py`
- Modify: `app/main.py`

- [ ] **Step 1: 用以下实现替换 `app/routers/knowledge_bases.py`**

```python
"""知识库模块路由：/api/v1/knowledge-bases。"""

from fastapi import APIRouter

from app.core.config import settings
from app.dependencies import CurrentTeamAdminOrLead, CurrentUser, DbSession
from app.schemas.common import ApiResponse, ModuleStatus
from app.schemas.knowledge import (
    KnowledgeCreateData,
    KnowledgeCreateRequest,
    KnowledgeIdRequest,
    KnowledgeItem,
    KnowledgePageData,
    KnowledgePageRequest,
    KnowledgeUpdateRequest,
)
from app.services.knowledge_service import knowledge_service

router = APIRouter(
    prefix=settings.api_v1_prefix + "/knowledge-bases",
    tags=["知识库"],
)


@router.get("/status", response_model=ApiResponse[ModuleStatus], summary="模块状态")
async def knowledge_status() -> ApiResponse[ModuleStatus]:
    return ApiResponse(
        data=ModuleStatus(module="knowledge-bases", detail="知识库管理路由已就绪")
    )


@router.post(
    "/create",
    response_model=ApiResponse[KnowledgeCreateData],
    summary="创建知识库",
    status_code=201,
)
async def create_knowledge_base(
    body: KnowledgeCreateRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[KnowledgeCreateData]:
    data = await knowledge_service.create(db, user, body)
    return ApiResponse(message="创建成功", data=data)


@router.post(
    "/page",
    response_model=ApiResponse[KnowledgePageData],
    summary="分页查询知识库",
)
async def page_knowledge_bases(
    body: KnowledgePageRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[KnowledgePageData]:
    data = await knowledge_service.page(db, user, body)
    return ApiResponse(data=data)


@router.post(
    "/getById",
    response_model=ApiResponse[KnowledgeItem],
    summary="获取知识库详情",
)
async def get_knowledge_base_by_id(
    body: KnowledgeIdRequest,
    db: DbSession,
    user: CurrentUser,
) -> ApiResponse[KnowledgeItem]:
    data = await knowledge_service.get_by_id(db, user, body)
    return ApiResponse(data=data)


@router.post(
    "/update",
    response_model=ApiResponse[None],
    summary="修改知识库",
)
async def update_knowledge_base(
    body: KnowledgeUpdateRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[None]:
    await knowledge_service.update(db, user, body)
    return ApiResponse(message="更新成功")


@router.post(
    "/delete",
    response_model=ApiResponse[None],
    summary="删除知识库",
)
async def delete_knowledge_base(
    body: KnowledgeIdRequest,
    db: DbSession,
    user: CurrentTeamAdminOrLead,
) -> ApiResponse[None]:
    await knowledge_service.delete(db, user, body)
    return ApiResponse(message="删除成功")
```

- [ ] **Step 2: 修改 `app/main.py` 的 import 与挂载**

在 `from app.routers import (` 块中增加 `knowledge_bases`：

```python
from app.routers import (
    admin,
    auth,
    conversations,
    health,
    knowledge_bases,
    messages,
    teams,
)
```

在 `app.include_router(admin.router)` 附近增加：

```python
app.include_router(knowledge_bases.router)
```

- [ ] **Step 3: 启动检查路由是否出现**

Run: `python -c "from app.main import app; paths=[r.path for r in app.routes]; print([p for p in paths if 'knowledge' in p])"`

Expected: 包含 `/api/v1/knowledge-bases/create`、`/page`、`/getById`、`/update`、`/delete`、`/status`

- [ ] **Step 4: 可选提交**

```bash
git add app/routers/knowledge_bases.py app/main.py
git commit -m "feat: expose knowledge base CRUD API routes"
```

---

### Task 7: 更新 README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 在 README「已挂载的 API 前缀」后、或「历史消息」一节前，增加知识库章节**

内容需覆盖：

1. 五个接口路径、权限、请求/响应示例（与 spec 一致）
2. 删除顺序：先 Milvus 再 MySQL；失败不删库
3. `.env` 中 `MILVUS_URI` / `MILVUS_COLLECTION`
4. 「当前进度」勾选知识库 CRUD

同时在依赖表 `CurrentUser` 附近补充：

| 依赖 | 含义 |
|------|------|
| `CurrentTeamAdminOrLead` | 已登录，且当前团队角色为 **admin** 或 **tech_lead** |

- [ ] **Step 2: 可选提交**

```bash
git add README.md
git commit -m "docs: document knowledge base APIs"
```

---

### Task 8: 手工验收清单

- [ ] **Step 1: 启动服务**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: 打开 http://127.0.0.1:8000/docs 确认五个接口可见**

- [ ] **Step 3: 用 admin/tech_lead Token 调用 create → 得到 id**

- [ ] **Step 4: 用 developer Token 调 create → 403**

- [ ] **Step 5: page / getById 对本团队数据正常；错误 id → 404**

- [ ] **Step 6: 同名再 create → 409**

- [ ] **Step 7: update 改名/描述；无字段 → 422**

- [ ] **Step 8: delete：Milvus 可达时成功；人为断掉 Milvus 时 MySQL 记录仍在且返回 503**

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| POST create + 仅返回 id | 2, 5, 6 |
| POST page + keyword | 2, 3, 5, 6 |
| POST getById | 2, 5, 6 |
| POST update 至少一项 | 2, 5, 6 |
| POST delete Milvus→MySQL | 4, 5, 6 |
| admin/tech_lead 写权限 | 2, 6 |
| 成员读权限 | 6 |
| Token 当前团队 | 5 |
| 重名 409 | 5 |
| 跨团队当 404 | 3, 5 |
| config / .env.example | 1 |
| README | 7 |
| main 挂载 | 6 |

## Self-Review Notes

- 无 TBD/占位步骤
- `count_by_team` 保留，避免解散团队逻辑回归
- Collection 不存在视为「无向量」成功；连接失败仍阻止删库——与验收「断掉 Milvus」一致
- Commit 步骤均为可选，遵循「用户未要求不提交」规则
