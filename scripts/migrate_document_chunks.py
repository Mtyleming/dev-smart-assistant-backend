"""一次性迁移：给已有 document_chunks 表补齐 chunk_id / knowledge_base_id / team_id。"""

import asyncio

from sqlalchemy import text

from app.core.database import engine


async def column_exists(conn, name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'document_chunks'
              AND COLUMN_NAME = :name
            """
        ),
        {"name": name},
    )
    return int(result.scalar_one()) > 0


async def main() -> None:
    async with engine.begin() as conn:
        if not await column_exists(conn, "chunk_id"):
            await conn.execute(
                text(
                    "ALTER TABLE document_chunks "
                    "ADD COLUMN chunk_id VARCHAR(128) NULL "
                    "COMMENT '业务切块ID' AFTER id"
                )
            )
            print("added chunk_id")
        else:
            print("chunk_id exists")

        if not await column_exists(conn, "knowledge_base_id"):
            await conn.execute(
                text(
                    "ALTER TABLE document_chunks "
                    "ADD COLUMN knowledge_base_id BIGINT NULL "
                    "COMMENT '所属知识库' AFTER content"
                )
            )
            print("added knowledge_base_id")
        else:
            print("knowledge_base_id exists")

        if not await column_exists(conn, "team_id"):
            await conn.execute(
                text(
                    "ALTER TABLE document_chunks "
                    "ADD COLUMN team_id BIGINT NULL "
                    "COMMENT '团队隔离' AFTER knowledge_base_id"
                )
            )
            print("added team_id")
        else:
            print("team_id exists")

        await conn.execute(
            text(
                "ALTER TABLE document_chunks "
                "MODIFY COLUMN collection_name VARCHAR(100) NOT NULL "
                "DEFAULT 'document_chunks'"
            )
        )

        await conn.execute(
            text(
                """
                UPDATE document_chunks dc
                INNER JOIN documents d ON d.id = dc.document_id
                INNER JOIN knowledge_bases kb ON kb.id = d.knowledge_base_id
                SET
                  dc.chunk_id = CONCAT(dc.document_id, '_', dc.chunk_index),
                  dc.knowledge_base_id = d.knowledge_base_id,
                  dc.team_id = kb.team_id
                WHERE dc.chunk_id IS NULL
                   OR dc.knowledge_base_id IS NULL
                   OR dc.team_id IS NULL
                """
            )
        )
        print("backfilled")

        orphan = await conn.execute(
            text(
                "DELETE FROM document_chunks "
                "WHERE chunk_id IS NULL "
                "OR knowledge_base_id IS NULL "
                "OR team_id IS NULL"
            )
        )
        print("deleted orphans", orphan.rowcount)

        await conn.execute(
            text(
                "ALTER TABLE document_chunks "
                "MODIFY COLUMN chunk_id VARCHAR(128) NOT NULL"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE document_chunks "
                "MODIFY COLUMN knowledge_base_id BIGINT NOT NULL"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE document_chunks "
                "MODIFY COLUMN team_id BIGINT NOT NULL"
            )
        )
        print("not null ok")

        for sql, label in [
            (
                "CREATE UNIQUE INDEX uk_document_chunk_id ON document_chunks (chunk_id)",
                "uk_document_chunk_id",
            ),
            (
                "CREATE INDEX idx_document_chunks_kb_id ON document_chunks (knowledge_base_id)",
                "idx_document_chunks_kb_id",
            ),
            (
                "CREATE INDEX idx_document_chunks_team_id ON document_chunks (team_id)",
                "idx_document_chunks_team_id",
            ),
        ]:
            try:
                await conn.execute(text(sql))
                print("index ok", label)
            except Exception as exc:
                print("index skip", label, exc)

        result = await conn.execute(text("SHOW COLUMNS FROM document_chunks"))
        for row in result.fetchall():
            print(row[0], row[1], row[2])


if __name__ == "__main__":
    asyncio.run(main())
