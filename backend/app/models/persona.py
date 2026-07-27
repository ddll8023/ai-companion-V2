"""人物理解数据模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, JSON, func

from app.core.base_model import BaseModel
from app.core.database import Base


class Observation(BaseModel):
    """记录来自用户消息的可追溯观察。"""

    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    observation_type = Column(String(32), nullable=False, index=True)
    dimension = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    source_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence = Column(String(512), nullable=False)
    embedding = Column(LargeBinary, nullable=True)
    reflected_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)

    __table_args__ = (CheckConstraint("observation_type IN ('content', 'expression', 'emotion', 'interaction')", name="ck_observation_type"),)


class Insight(BaseModel):
    """记录由观察归纳出的稳定人物洞见。"""

    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_type = Column(String(32), nullable=False, default="pattern")
    dimension = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    abstraction_level = Column(Integer, nullable=False, default=1)
    maturity = Column(String(16), nullable=False, default="emerging", index=True)
    confidence = Column(Integer, nullable=False, default=20)
    stability_score = Column(Integer, nullable=False, default=20)
    support_count = Column(Integer, nullable=False, default=0)
    contradiction_count = Column(Integer, nullable=False, default=0)
    user_override = Column(Boolean, nullable=False, default=False)
    supersedes_insight_id = Column(Integer, ForeignKey("insights.id", ondelete="SET NULL"), nullable=True)
    version = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("maturity IN ('emerging', 'developing', 'established', 'declining', 'superseded', 'rejected')", name="ck_insight_maturity"),
        CheckConstraint("confidence >= 0 AND confidence <= 100", name="ck_insight_confidence"),
        CheckConstraint("stability_score >= 0 AND stability_score <= 100", name="ck_insight_stability"),
    )


class InsightEvidence(Base):
    """连接洞见与观察的证据关系。"""

    __tablename__ = "insight_evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_id = Column(Integer, ForeignKey("insights.id", ondelete="CASCADE"), nullable=False, index=True)
    observation_id = Column(Integer, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(16), nullable=False, default="supports")
    weight = Column(Integer, nullable=False, default=1)
    is_valid = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class InsightRelation(Base):
    """记录洞见之间的支持、矛盾、细化和取代关系。"""

    __tablename__ = "insight_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_id = Column(Integer, ForeignKey("insights.id", ondelete="CASCADE"), nullable=False, index=True)
    related_insight_id = Column(Integer, ForeignKey("insights.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(16), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class InsightRevision(Base):
    """保存洞见修改前的版本。"""

    __tablename__ = "insight_revisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insight_id = Column(Integer, ForeignKey("insights.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_content = Column(Text, nullable=False)
    previous_maturity = Column(String(16), nullable=True)
    previous_confidence = Column(Integer, nullable=True)
    changed_by = Column(String(16), nullable=False, default="system")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PersonaState(BaseModel):
    """记录短期、情境化的人物状态。"""

    __tablename__ = "persona_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state_type = Column(String(32), nullable=False, index=True)
    content = Column(Text, nullable=False)
    intensity = Column(Integer, nullable=False, default=50)
    valid_from = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True, index=True)
    source_session_id = Column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)


class PersonaDocument(BaseModel):
    """保存人物侧写文档的全量版本。"""

    __tablename__ = "persona_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False, default="")
    structured_sections = Column(JSON, nullable=False, default=dict)
    user_edited_sections = Column(JSON, nullable=False, default=dict)
    cited_insight_ids = Column(JSON, nullable=False, default=list)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    change_summary = Column(String(512), nullable=True)
    edited_by = Column(String(16), nullable=False, default="system")
    is_pending_review = Column(Boolean, nullable=False, default=False)
