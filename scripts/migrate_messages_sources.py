"""一次性迁移：为 messages 表增加 sources JSON 字段。"""

import asyncio

from sqlalchemy import text

from app.core.database import async_session_factory


async def main() -> None:
    async with async_session_factory() as db:
        rows = await db.execute(text("SHOW COLUMNS FROM messages LIKE 'sources'"))
        if rows.first():
            print("sources column already exists")
            return
        await db.execute(
            text(
                "ALTER TABLE messages "
                "ADD COLUMN sources JSON NULL "
                "COMMENT 'RAG 引用 sources，助手消息可空' "
                "AFTER content_type"
            )
        )
        await db.commit()
        print("sources column added")


if __name__ == "__main__":
    asyncio.run(main())
