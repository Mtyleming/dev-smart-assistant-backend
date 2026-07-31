"""超级管理员判定（不依赖 users 表扩展字段）。"""

from app.core.config import settings


def is_super_admin(user_id: int | str) -> bool:
    """判断用户是否为超级管理员。"""
    return int(user_id) == settings.super_admin_user_id
