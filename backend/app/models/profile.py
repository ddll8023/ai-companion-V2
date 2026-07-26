"""画像数据模型。

Profile（画像特征）、ProfileSource（来源证据）、ProfileRevision（修订历史）三张表，
构成完整的画像生命周期管理。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.base_model import BaseModel
from app.core.database import Base


class Profile(BaseModel):
    """画像特征表。"""

    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    category = Column(
        String(32),
        nullable=False,
        default="other",
        index=True,
        comment=(
            "画像类别: "
            "communication_preference/work_habit/learning_preference/"
            "interest/decision_preference/time_habit/"
            "long_term_goal/work_pattern/other"
        ),
    )
    content = Column(Text, nullable=False, comment="画像正文")
    confidence = Column(Integer, nullable=False, default=0, comment="置信度 0-100")
    status = Column(
        String(16),
        nullable=False,
        default="candidate",
        index=True,
        comment="状态: candidate/confirmed/corrected/rejected/deleted",
    )
    is_auto_extracted = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否自动提取: False=手动, True=LLM 自动提取",
    )
    version = Column(Integer, nullable=False, default=1, comment="版本号，纠正后递增")
    supersedes_profile_id = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        comment="候选修订版指向的被修订画像 ID（确认后旧画像自动转 rejected）",
    )
    error_message = Column(String(256), nullable=True, comment="错误信息（提取失败时记录）")

    def __repr__(self):
        return (
            f"<Profile(id={self.id}, category='{self.category}', "
            f"status='{self.status}')>"
        )


class ProfileSource(Base):
    """画像来源表。

    记录每条画像的来源证据，支持来源追溯。
    """

    __tablename__ = "profile_sources"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    profile_id = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联画像 ID",
    )
    source_type = Column(
        String(16),
        nullable=False,
        comment="来源类型: memory/activity/user/extraction",
    )
    memory_id = Column(Integer, nullable=True, comment="来源记忆 ID（可为空）")
    content_preview = Column(
        String(256), nullable=True, comment="来源内容预览（前 N 字符）",
    )
    evidence_text = Column(
        String(512), nullable=True, comment="LLM 提取时关联的记忆原文证据",
    )
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return (
            f"<ProfileSource(id={self.id}, profile_id={self.profile_id}, "
            f"type='{self.source_type}', memory_id={self.memory_id})>"
        )


class ProfileRevision(Base):
    """画像修订历史表。

    记录纠正前的旧版本内容，支持修订追溯。
    """

    __tablename__ = "profile_revisions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    profile_id = Column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="关联画像 ID",
    )
    previous_category = Column(String(32), nullable=True, comment="旧类别")
    previous_content = Column(Text, nullable=False, comment="旧正文")
    previous_confidence = Column(Integer, nullable=True, comment="旧置信度")
    previous_status = Column(String(16), nullable=True, comment="旧状态")
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
            f"<ProfileRevision(id={self.id}, profile_id={self.profile_id}, "
            f"changed_by='{self.changed_by}')>"
        )
