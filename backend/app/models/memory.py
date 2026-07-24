"""记忆数据模型。

记忆、记忆来源、记忆修订历史三张表，构成完整的记忆生命周期管理。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func

from app.core.base_model import BaseModel
from app.core.database import Base


class Memory(BaseModel):
    """记忆表。"""

    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    content = Column(Text, nullable=False, comment="记忆正文内容")
    type = Column(
        String(32),
        nullable=False,
        default="fact",
        comment=(
            "记忆类型: fact=事实, preference=偏好, event=事件, "
            "goal=目标/意图（语义类别，非 Goal 表）, habit=习惯"
        ),
    )
    importance = Column(
        Integer, nullable=False, default=0, comment="重要性 0-10，数值越高越重要",
    )
    status = Column(
        String(16),
        nullable=False,
        default="candidate",
        index=True,
        comment="状态: candidate/confirmed/corrected/rejected/deleted",
    )
    session_id = Column(
        Integer,
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="来源会话 ID（可选）",
    )
    source_version = Column(
        String(64), nullable=True, comment="来源内容版本号，用于校验内容是否过时",
    )
    version = Column(
        Integer, nullable=False, default=1, comment="版本号，用户纠正后递增",
    )
    embedding = Column(
        LargeBinary, nullable=True, comment="嵌入向量（512 × float32，L2 归一化，BLOB 存储）",
    )
    error_message = Column(String(256), nullable=True, comment="错误信息（提取失败时记录）")

    __table_args__ = (
        CheckConstraint("importance >= 0 AND importance <= 10", name="ck_memory_importance"),
        CheckConstraint("status IN ('candidate', 'confirmed', 'corrected', 'rejected', 'deleted')", name="ck_memory_status"),
        CheckConstraint("type IN ('fact', 'preference', 'event', 'goal', 'habit')", name="ck_memory_type"),
    )

    def __repr__(self):
        return f"<Memory(id={self.id}, type='{self.type}', status='{self.status}')>"


class MemorySource(Base):
    """记忆来源表。

    记录每条记忆的来源证据，支持来源追溯。
    """

    __tablename__ = "memory_sources"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    memory_id = Column(
        Integer,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联记忆 ID",
    )
    source_type = Column(
        String(16),
        nullable=False,
        comment="来源类型: message/activity/user",
    )
    source_id = Column(Integer, nullable=False, comment="来源记录 ID")
    content_preview = Column(
        String(256), nullable=True, comment="来源内容预览（前 N 字符，不含完整正文）",
    )
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return (
            f"<MemorySource(id={self.id}, memory_id={self.memory_id}, "
            f"type='{self.source_type}', source_id={self.source_id})>"
        )


class MemoryRevision(Base):
    """记忆修订历史表。

    记录用户纠正前的旧版本内容，支持修订追溯。
    """

    __tablename__ = "memory_revisions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    memory_id = Column(
        Integer,
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联记忆 ID",
    )
    previous_content = Column(Text, nullable=False, comment="修改前的记忆正文")
    previous_type = Column(String(32), nullable=True, comment="修改前的记忆类型")
    previous_importance = Column(Integer, nullable=True, comment="修改前的重要性")
    changed_by = Column(
        String(16),
        nullable=False,
        default="user",
        comment="变更方: user/system",
    )
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return (
            f"<MemoryRevision(id={self.id}, memory_id={self.memory_id}, "
            f"changed_by='{self.changed_by}')>"
        )


class MemoryReference(Base):
    """记忆引用表。

    记录每条助手消息实际引用了哪些记忆，用于追溯和审计。
    """

    __tablename__ = "memory_references"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    message_id = Column(
        Integer,
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联消息 ID（助手回复）",
    )
    memory_id = Column(
        Integer,
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联记忆 ID",
    )
    memory_content_preview = Column(String(256), nullable=True, comment="记忆内容预览（前 N 字符）")
    relevance_score = Column(Integer, nullable=True, comment="相关度分数 0-100")
    rank = Column(Integer, nullable=True, comment="在检索结果中的排名")
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return f"<MemoryReference(id={self.id}, message_id={self.message_id}, memory_id={self.memory_id})>"
