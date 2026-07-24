"""目标和任务数据模型。

目标（Goal）和任务（Task）两张表，支持 AI 建议生成和用户确认流程。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func

from app.core.base_model import BaseModel


class Goal(BaseModel):
    """目标表。"""

    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    title = Column(String(256), nullable=False, comment="目标标题")
    description = Column(Text, nullable=True, comment="目标描述")
    status = Column(
        SmallInteger,
        nullable=False,
        default=0,
        index=True,
        comment="状态: 0=进行中, 1=已完成, 2=已放弃",
    )
    target_date = Column(DateTime, nullable=True, comment="目标完成日期")

    __table_args__ = (
        CheckConstraint("status IN (0, 1, 2)", name="ck_goal_status"),
    )

    def __repr__(self):
        return f"<Goal(id={self.id}, title='{self.title}', status={self.status})>"


class Task(BaseModel):
    """任务表。

    支持以下场景：
    - 手动创建的任务（is_from_suggestion=0）
    - AI 建议生成的任务（is_from_suggestion=1），用户确认后才成为正式任务
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    goal_id = Column(
        Integer,
        ForeignKey("goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联目标 ID",
    )
    title = Column(String(256), nullable=False, comment="任务标题")
    description = Column(Text, nullable=True, comment="任务描述")
    status = Column(
        SmallInteger,
        nullable=False,
        default=0,
        index=True,
        comment="状态: 0=待处理, 1=进行中, 2=已完成, 3=已放弃",
    )
    priority = Column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="优先级: 0=无, 1=低, 2=中, 3=高, 4=紧急",
    )
    is_from_suggestion = Column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="是否来自 AI 建议: 0=否, 1=是",
    )
    suggestion_status = Column(
        SmallInteger,
        nullable=False,
        default=0,
        index=True,
        comment="建议状态: 0=无, 1=待确认, 2=已接受, 3=已拒绝",
    )
    suggestion_data = Column(
        Text,
        nullable=True,
        comment="原始建议数据（JSON 字符串，含建议理由等）",
    )

    __table_args__ = (
        CheckConstraint("status IN (0, 1, 2, 3)", name="ck_task_status"),
        CheckConstraint("priority IN (0, 1, 2, 3, 4)", name="ck_task_priority"),
        CheckConstraint("is_from_suggestion IN (0, 1)", name="ck_task_is_suggestion"),
        CheckConstraint("suggestion_status IN (0, 1, 2, 3)", name="ck_task_suggestion_status"),
    )

    def __repr__(self):
        return (
            f"<Task(id={self.id}, title='{self.title}', "
            f"status={self.status}, suggestion_status={self.suggestion_status})>"
        )
