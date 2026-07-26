"""对话轮次、会话摘要与 AI 内容项模型。"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text

from app.core.base_model import BaseModel


class ConversationTurn(BaseModel):
    __tablename__ = "conversation_turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    assistant_message_id = Column(Integer, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, unique=True)
    status = Column(String(16), nullable=False, default="generating", comment="generating/completed/aborted/failed")


class SessionSummary(BaseModel):
    __tablename__ = "session_summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    from_turn_id = Column(Integer, ForeignKey("conversation_turns.id", ondelete="SET NULL"), nullable=True)
    to_turn_id = Column(Integer, ForeignKey("conversation_turns.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    source_version = Column(String(64), nullable=True)


class AiArtifact(BaseModel):
    __tablename__ = "ai_artifacts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    assistant_message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    title = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="saved", comment="saved/adopted/dismissed")
    __table_args__ = (Index("ix_ai_artifacts_status", "status"),)
