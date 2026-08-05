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


class ConversationMode(str, enum.Enum):
    """对话模式：智能问答 / 代码辅助 / 文档生成。"""

    qa = "qa"
    code = "code"
    doc = "doc"


class MessageRole(str, enum.Enum):
    """消息角色：用户 / 助手 / 系统。"""

    user = "user"
    assistant = "assistant"
    system = "system"


class MessageContentType(str, enum.Enum):
    """消息内容类型。"""

    text = "text"
    code = "code"


class DocumentStatus(str, enum.Enum):
    """文档处理状态。"""

    uploading = "uploading"
    uploaded = "uploaded"
    parsing = "parsing"
    completed = "completed"
    failed = "failed"
    deleting = "deleting"
    deleted = "deleted"


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
    documents = relationship("Document", back_populates="knowledge_base")


class Document(Base):
    """知识库文档：上传文件与解析状态。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("knowledge_bases.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            values_callable=lambda statuses: [item.value for item in statuses],
        ),
        nullable=False,
        server_default=DocumentStatus.uploading.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")


class Conversation(Base):
    """对话会话：用户在当前团队下的一次多轮交互。"""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[ConversationMode] = mapped_column(
        Enum(
            ConversationMode,
            values_callable=lambda modes: [mode.value for mode in modes],
        ),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id"), nullable=False, index=True
    )
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

    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """对话消息：一次问答中的单条记录。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[MessageContentType] = mapped_column(
        Enum(
            MessageContentType,
            values_callable=lambda types: [item.value for item in types],
        ),
        nullable=False,
        server_default=MessageContentType.text.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    is_delete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="0"
    )

    conversation = relationship("Conversation", back_populates="messages")
