"""对话数据模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class ChatSession(Base):
    """会话表。"""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    title = Column(String(128), nullable=False, default="新对话", comment="会话标题")
    model_name = Column(String(128), nullable=True, comment="使用的模型名称")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间",
    )

    def __repr__(self):
        return f"<ChatSession(id={self.id}, title='{self.title}')>"


class Message(Base):
    """消息表。"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    session_id = Column(
        Integer,
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话 ID",
    )
    role = Column(String(16), nullable=False, comment="角色: user/assistant/system")
    content = Column(Text, nullable=False, comment="消息内容")
    status = Column(
        String(16), nullable=False, default="completed", comment="状态: generating/completed/aborted/failed",
    )
    error_message = Column(String(256), nullable=True, comment="错误信息（可选）")
    model_name = Column(String(128), nullable=True, comment="生成此消息的模型名称")
    token_count = Column(Integer, nullable=True, comment="token 数量（可选）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', status='{self.status}')>"
