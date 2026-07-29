"""核心业务模型（骨架占位，后续按模块补全字段）。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Team(Base):
    """团队：数据隔离的基本单位。"""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    users = relationship("User", back_populates="team")
    knowledge_bases = relationship("KnowledgeBase", back_populates="team")


class User(Base):
    """用户：归属某个团队。"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    team = relationship("Team", back_populates="users")


class KnowledgeBase(Base):
    """知识库：一个团队可拥有多个知识库。"""

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    team_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teams.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    team = relationship("Team", back_populates="knowledge_bases")
