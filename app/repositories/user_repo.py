"""用户数据访问。"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base_models import User


class UserRepository:
    """用户表 CRUD 封装。"""

    async def get_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        """按 ID 查询用户。"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email_or_username(
        self, db: AsyncSession, email: str, username: str
    ) -> User | None:
        """按邮箱或用户名查询，用于注册去重。"""
        result = await db.execute(
            select(User).where(or_(User.email == email, User.username == username))
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, db: AsyncSession, number: str) -> User | None:
        """按用户名或邮箱查询，用于登录。"""
        result = await db.execute(
            select(User).where(or_(User.email == number, User.username == number))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        username: str,
        email: str,
        password_hash: str,
    ) -> User:
        """创建用户记录，id 由数据库自增生成。"""
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
        )
        db.add(user)
        await db.flush()
        return user


user_repo = UserRepository()
