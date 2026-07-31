"""核心业务模型（与 dev_assistant 库表结构一致）。"""

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TeamMemberRole(str, enum.Enum):
    """团队内角色，对应 team_members.role 枚举。"""

    admin = "admin"
    tech_lead = "tech_lead"
    developer = "developer"


class Team(Base):
    """团队：数据隔离的基本单位。"""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
    )
    is_delete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )

    members = relationship("TeamMember", back_populates="team")
    knowledge_bases = relationship("KnowledgeBase", back_populates="team")


class TeamMember(Base):
    """团队成员关系：用户在某团队中的角色。"""

    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uk_team_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[TeamMemberRole] = mapped_column(
        Enum(
            TeamMemberRole,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        nullable=False,
        server_default=TeamMemberRole.developer.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")


class User(Base):
    """用户账号（与团队多对多，通过 team_members 关联）。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    team_memberships = relationship("TeamMember", back_populates="user")


class KnowledgeBase(Base):
    """知识库：一个团队可拥有多个知识库。"""

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    team = relationship("Team", back_populates="knowledge_bases")
