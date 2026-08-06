"""Milvus 向量检索、写入与清理封装。"""

import asyncio
import logging
from typing import Any

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# content 字段最大长度（与 Schema VARCHAR 一致）
_CONTENT_MAX_LENGTH = 8192
_CHUNK_ID_MAX_LENGTH = 128


def _is_milvus_unavailable(exc: BaseException) -> bool:
    """判断是否为 Milvus 连不上（服务未启动 / 地址错误）。"""
    text = str(exc).lower()
    markers = (
        "fail connecting",
        "connection refused",
        "unavailable",
        "server unavailable",
        "10061",
    )
    return any(marker in text for marker in markers)


def _raise_milvus_error(
    *,
    code: int,
    default_message: str,
    exc: BaseException,
) -> None:
    """统一抛出 Milvus 相关业务异常；连不上时给出可操作提示。"""
    if _is_milvus_unavailable(exc):
        raise AppException(
            code=code,
            message=(
                f"向量数据库未启动或无法连接（{settings.milvus_uri}）。"
                "请确认 milvus-server 已启动，或使用 "
                "docker compose -f docker-compose.milvus.yml up -d"
            ),
            status_code=503,
        ) from exc
    raise AppException(
        code=code,
        message=default_message,
        status_code=503,
    ) from exc


class VectorRepository:
    """向量库操作：切块写入、检索、按文档/知识库清理。"""

    async def search(
        self,
        question: str,
        team_id: str,
        kb_ids: list[str],
    ) -> list[dict]:
        """按问题与知识库范围检索切块（占位，后续 RAG 接入）。"""
        _ = (question, team_id, kb_ids)
        return []

    async def upsert_chunks(self, rows: list[dict[str, Any]]) -> None:
        """批量写入切块向量；自动确保 Collection 存在。

        每行需含：chunk_id, document_id, chunk_index, content, vector,
        knowledge_base_id, team_id。
        """
        if not rows:
            return
        try:
            await asyncio.to_thread(self._upsert_chunks_sync, rows)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Milvus 写入切块失败 count=%s", len(rows))
            _raise_milvus_error(
                code=50302,
                default_message="向量数据写入失败",
                exc=exc,
            )

    async def delete_by_document(self, team_id: int, document_id: int) -> None:
        """删除某文档在 Milvus 中的全部切块向量。

        过滤：document_id == id AND team_id == team_id
        失败时抛出 AppException，调用方不得继续改 MySQL。
        """
        try:
            await asyncio.to_thread(
                self._delete_by_document_sync, int(team_id), int(document_id)
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "Milvus 按文档清理失败 team_id=%s document_id=%s",
                team_id,
                document_id,
            )
            _raise_milvus_error(
                code=50301,
                default_message="向量数据清理失败，文档未删除",
                exc=exc,
            )

    async def delete_by_knowledge_base(
        self, team_id: int, knowledge_base_id: int
    ) -> None:
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
            _raise_milvus_error(
                code=50301,
                default_message="向量数据清理失败，知识库未删除",
                exc=exc,
            )

    def _upsert_chunks_sync(self, rows: list[dict[str, Any]]) -> None:
        """同步写入（在线程池中执行）。"""
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        collection = settings.milvus_collection
        self._ensure_collection_sync(client, collection)
        self._ensure_vector_index_sync(client, collection)

        data: list[dict[str, Any]] = []
        for row in rows:
            content = str(row["content"] or "")
            if len(content) > _CONTENT_MAX_LENGTH:
                content = content[:_CONTENT_MAX_LENGTH]
            chunk_id = str(row["chunk_id"])
            if len(chunk_id) > _CHUNK_ID_MAX_LENGTH:
                chunk_id = chunk_id[:_CHUNK_ID_MAX_LENGTH]
            data.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": int(row["document_id"]),
                    "chunk_index": int(row["chunk_index"]),
                    "content": content,
                    "vector": list(row["vector"]),
                    "knowledge_base_id": int(row["knowledge_base_id"]),
                    "team_id": int(row["team_id"]),
                }
            )
        client.insert(collection_name=collection, data=data)
        # 写入后确保可查询（删除文档时要 query）
        self._ensure_loaded_sync(client, collection)

    def _ensure_collection_sync(self, client: Any, collection: str) -> None:
        """Collection 不存在则按约定 Schema 创建。"""
        if client.has_collection(collection_name=collection):
            return

        from pymilvus import DataType

        dim = int(settings.embedding_dimensions)
        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field(
            "chunk_id", DataType.VARCHAR, max_length=_CHUNK_ID_MAX_LENGTH
        )
        schema.add_field("document_id", DataType.INT64)
        schema.add_field("chunk_index", DataType.INT64)
        schema.add_field(
            "content", DataType.VARCHAR, max_length=_CONTENT_MAX_LENGTH
        )
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field("knowledge_base_id", DataType.INT64)
        schema.add_field("team_id", DataType.INT64)

        client.create_collection(
            collection_name=collection,
            schema=schema,
        )
        logger.info(
            "已创建 Milvus collection=%s dim=%s", collection, dim
        )
        self._ensure_vector_index_sync(client, collection)

    def _has_vector_index(self, client: Any, collection: str) -> bool:
        """检查 vector 字段是否已有索引。"""
        try:
            indexes = client.list_indexes(
                collection_name=collection, field_name="vector"
            )
            return bool(indexes)
        except Exception as exc:
            logger.debug("list_indexes 失败: %s", exc)
            return False

    def _ensure_vector_index_sync(self, client: Any, collection: str) -> None:
        """确保 vector 字段有索引（milvus-server 无索引时无法 load/query）。"""
        if self._has_vector_index(client, collection):
            return

        # milvus-server 通常只支持 L2/IP；正式 Milvus 还支持 COSINE
        # FLAT 对本地 milvus-server 兼容性最好
        candidates: list[tuple[str, str, dict[str, Any]]] = [
            ("FLAT", "L2", {}),
            ("FLAT", "IP", {}),
            ("IVF_FLAT", "L2", {"nlist": 128}),
            ("IVF_FLAT", "IP", {"nlist": 128}),
            ("AUTOINDEX", "L2", {}),
            ("AUTOINDEX", "COSINE", {}),
            ("FLAT", "COSINE", {}),
        ]
        last_error: Exception | None = None
        for index_type, metric_type, params in candidates:
            try:
                index_params = client.prepare_index_params()
                index_params.add_index(
                    field_name="vector",
                    index_type=index_type,
                    metric_type=metric_type,
                    params=params,
                )
                client.create_index(
                    collection_name=collection, index_params=index_params
                )
                logger.info(
                    "已创建向量索引 collection=%s type=%s metric=%s",
                    collection,
                    index_type,
                    metric_type,
                )
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "创建向量索引失败 collection=%s type=%s metric=%s: %s",
                    collection,
                    index_type,
                    metric_type,
                    exc,
                )

        raise RuntimeError(
            f"无法为 collection={collection} 创建向量索引"
        ) from last_error

    def _ensure_loaded_sync(self, client: Any, collection: str) -> None:
        """确保索引存在并加载到内存，供 query/delete 使用。"""
        self._ensure_vector_index_sync(client, collection)
        try:
            client.load_collection(collection_name=collection)
            return
        except Exception as first_exc:
            logger.warning("load_collection 首次失败，尝试重建加载: %s", first_exc)
        try:
            client.release_collection(collection_name=collection)
        except Exception:
            pass
        self._ensure_vector_index_sync(client, collection)
        client.load_collection(collection_name=collection)

    def _delete_by_document_sync(self, team_id: int, document_id: int) -> None:
        """同步按文档删除（在线程池中执行）。"""
        expr = f"document_id == {document_id} and team_id == {team_id}"
        self._delete_by_filter_sync(expr)

    def _delete_sync(self, team_id: int, knowledge_base_id: int) -> None:
        """同步按知识库删除（在线程池中执行）。"""
        expr = (
            f"knowledge_base_id == {knowledge_base_id} and team_id == {team_id}"
        )
        self._delete_by_filter_sync(expr)

    def _delete_by_filter_sync(self, filter_expr: str) -> None:
        """按标量条件删除：先 query 出主键，再按 ids 删除。

        milvus-server / Milvus Lite 的 delete 往往只支持主键条件
        （报错 only pk ... supported），不能直接用 document_id 等字段过滤删除。
        """
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        collection = settings.milvus_collection
        if not client.has_collection(collection_name=collection):
            logger.warning("Milvus collection 不存在，跳过清理: %s", collection)
            return

        self._ensure_loaded_sync(client, collection)

        rows = client.query(
            collection_name=collection,
            filter=filter_expr,
            output_fields=["id"],
        )
        ids = [row["id"] for row in rows if row.get("id") is not None]
        if not ids:
            logger.info("Milvus 无匹配切块可删 filter=%s", filter_expr)
            return

        # 按批删除，避免一次 ids 过大
        batch_size = 1000
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            client.delete(collection_name=collection, ids=batch)
        logger.info(
            "Milvus 已按主键删除切块 count=%s filter=%s", len(ids), filter_expr
        )


vector_repo = VectorRepository()
