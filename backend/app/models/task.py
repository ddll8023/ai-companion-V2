"""后台任务数据模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class BackgroundTask(Base):
    """后台任务表。"""

    __tablename__ = "background_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    task_type = Column(String(64), nullable=False, index=True, comment="任务类型，如 'memory.extract'、'index.update'")
    status = Column(
        String(16),
        nullable=False,
        default="pending",
        index=True,
        comment="状态: pending/processing/completed/retrying/failed/cancelled",
    )
    payload = Column(Text, nullable=True, comment="任务参数（JSON 字符串）")
    dedup_key = Column(String(128), nullable=True, index=True, comment="去重键（用于防止重复创建）")
    priority = Column(Integer, nullable=False, default=0, comment="优先级，数值越大越优先")
    retry_count = Column(Integer, nullable=False, default=0, comment="已重试次数")
    max_retries = Column(Integer, nullable=False, default=3, comment="最大重试次数")
    source_version = Column(String(64), nullable=True, comment="来源内容版本号，用于校验内容是否过时")
    error_message = Column(Text, nullable=True, comment="错误信息")
    result = Column(Text, nullable=True, comment="执行结果（JSON 字符串）")
    scheduled_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="计划执行时间（立即执行则使用创建时间）",
    )
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间",
    )

    def __repr__(self):
        return f"<BackgroundTask(id={self.id}, type='{self.task_type}', status='{self.status}')>"
