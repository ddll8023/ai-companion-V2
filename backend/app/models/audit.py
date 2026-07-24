"""审计记录数据模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, func

from app.core.database import Base


class AuditLog(Base):
    """审计日志表。"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    action = Column(String(64), nullable=False, index=True, comment="操作类型，如 'memory.delete', 'model.config.save'")
    target_type = Column(String(64), nullable=True, index=True, comment="操作对象类型，如 'memory', 'session'")
    target_id = Column(BigInteger, nullable=True, comment="操作对象 ID")
    actor_id = Column(Integer, nullable=True, index=True, comment="操作用户 ID")
    actor_name = Column(String(64), nullable=True, comment="操作用户名称")
    ip_address = Column(String(45), nullable=True, comment="客户端 IP 地址")
    summary = Column(String(256), nullable=True, comment="操作摘要（不含敏感正文）")
    detail = Column(Text, nullable=True, comment="操作补充信息（JSON 字符串，不含敏感正文）")
    result = Column(Integer, nullable=False, default=0, comment="操作结果，0=成功，1=失败")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")

    __table_args__ = (
        Index("ix_audit_logs_created_at_action", "created_at", "action"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}')>"
