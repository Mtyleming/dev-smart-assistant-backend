"""用户与团队相关业务。"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import user_repo


class UserService:
    """用户业务逻辑。"""

    async def get_profile(self, db: AsyncSession, user: dict[str, Any]) -> dict:
        """返回当前用户资料（开发阶段直接回传依赖注入的用户）。"""
        _ = (db, user_repo)
        return {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "team_id": user["team_id"],
        }


user_service = UserService()
