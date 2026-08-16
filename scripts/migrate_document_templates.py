"""一次性迁移：给 document_templates 补 version 列，并创建/校正历史版本表。"""

import asyncio

from sqlalchemy import text

from app.core.database import engine


async def column_exists(conn, table: str, name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
              AND COLUMN_NAME = :name
            """
        ),
        {"table": table, "name": name},
    )
    return int(result.scalar_one()) > 0


async def table_exists(conn, name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :name
            """
        ),
        {"name": name},
    )
    return int(result.scalar_one()) > 0


async def table_collation(conn, name: str) -> str | None:
    result = await conn.execute(
        text(
            """
            SELECT TABLE_COLLATION FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :name
            """
        ),
        {"name": name},
    )
    value = result.scalar_one_or_none()
    return str(value) if value else None


async def main() -> None:
    async with engine.begin() as conn:
        if not await table_exists(conn, "document_templates"):
            print("document_templates 不存在，跳过（启动时 create_all 会建表）")
            return

        if not await column_exists(conn, "document_templates", "version"):
            await conn.execute(
                text(
                    "ALTER TABLE document_templates "
                    "ADD COLUMN version INT NOT NULL DEFAULT 1 "
                    "COMMENT '模板版本号，更新时递增' AFTER created_by"
                )
            )
            print("added document_templates.version")
        else:
            print("document_templates.version exists")

        if not await table_exists(conn, "document_template_versions"):
            await conn.execute(
                text(
                    """
                    CREATE TABLE document_template_versions (
                      id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                      template_id BIGINT NOT NULL COMMENT '关联 document_templates.id',
                      version INT NOT NULL COMMENT '被归档的版本号',
                      name VARCHAR(200) NOT NULL COMMENT '当时的模板名称',
                      type ENUM('api_doc','module_doc','changelog','getting_started','custom')
                        NOT NULL COMMENT '当时的模板类型',
                      content TEXT NOT NULL COMMENT '当时的模板内容',
                      team_id BIGINT NULL COMMENT '所属团队',
                      created_by BIGINT NULL COMMENT '原创建者',
                      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '归档时间',
                      KEY ix_document_template_versions_template_id (template_id),
                      CONSTRAINT document_template_versions_ibfk_1
                        FOREIGN KEY (template_id) REFERENCES document_templates (id)
                        ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                      COMMENT='文档模板历史版本'
                    """
                )
            )
            print("created document_template_versions")
        else:
            print("document_template_versions exists")
            collation = await table_collation(conn, "document_template_versions")
            # SQLAlchemy create_all 可能按连接默认字符集建成 utf8mb3，与主表 utf8mb4 不一致
            if collation and not str(collation).lower().startswith("utf8mb4"):
                await conn.execute(
                    text(
                        "ALTER TABLE document_template_versions "
                        "CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
                print(
                    f"converted document_template_versions collation "
                    f"{collation} -> utf8mb4_unicode_ci"
                )
            else:
                print(f"document_template_versions collation={collation}")


if __name__ == "__main__":
    asyncio.run(main())
