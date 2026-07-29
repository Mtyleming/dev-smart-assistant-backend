"""用户数据访问。"""

from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    """用户表 CRUD 封装（骨架占位）。"""

    async def get_by_id(self, db: AsyncSession, user_id: str) -> None:
        """按 ID 查询用户，后续接入真实查询。"""
        _ = (db, user_id)
        return None


user_repo = UserRepository()
