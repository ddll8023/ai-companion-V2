"""数据治理数据模型。

DataExport（导出记录）、BackupRecord（备份记录）、RetentionPolicy（保留策略）三张表。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, func

from app.core.base_model import BaseModel
from app.core.database import Base


class DataExport(Base):
    """数据导出记录表。

    记录每次数据导出的时间、范围、状态和文件位置。
    """

    __tablename__ = "data_exports"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    export_type = Column(
        String(16),
        nullable=False,
        default="full",
        comment="导出类型: full=全部, partial=部分",
    )
    scope = Column(
        Text,
        nullable=True,
        comment="导出范围（JSON 字符串，如包含的模块列表）",
    )
    start_time = Column(DateTime, nullable=True, comment="开始时间（可选时间范围筛选）")
    end_time = Column(DateTime, nullable=True, comment="结束时间（可选时间范围筛选）")
    status = Column(
        String(16),
        nullable=False,
        default="completed",
        comment="状态: completed=完成, failed=失败",
    )
    file_path = Column(String(512), nullable=True, comment="导出文件路径（导出失败时可为空）")
    file_size_bytes = Column(BigInteger, nullable=True, comment="导出文件大小（字节）")
    record_count = Column(Integer, nullable=True, comment="导出记录数")
    error_message = Column(String(256), nullable=True, comment="错误信息")
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return f"<DataExport(id={self.id}, type='{self.export_type}', status='{self.status}')>"


class BackupRecord(Base):
    """数据库备份记录表。

    记录每次备份的创建时间、文件位置和恢复历史。
    """

    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    backup_type = Column(
        String(16),
        nullable=False,
        default="manual",
        comment="备份类型: manual=手动, auto=自动",
    )
    file_path = Column(String(512), nullable=False, comment="备份文件路径")
    file_size_bytes = Column(BigInteger, nullable=True, comment="备份文件大小（字节）")
    status = Column(
        String(16),
        nullable=False,
        default="completed",
        comment="状态: completed=完成, failed=失败, restoring=恢复中, restored=已恢复",
    )
    error_message = Column(String(256), nullable=True, comment="错误信息")
    restored_at = Column(DateTime, nullable=True, comment="恢复时间（如果被用于恢复）")
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return f"<BackupRecord(id={self.id}, type='{self.backup_type}', status='{self.status}')>"


class RetentionPolicy(BaseModel):
    """数据保留策略表。

    定义各类数据的保留期限和清理规则。
    """

    __tablename__ = "retention_policies"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    target_type = Column(
        String(32),
        nullable=False,
        index=True,
        unique=True,
        comment="目标数据类型: activities/messages/memories/profiles/audit_logs/backups",
    )
    retention_days = Column(
        Integer,
        nullable=False,
        default=90,
        comment="保留天数（超过此天数的数据将被清理）",
    )
    is_enabled = Column(
        Boolean, nullable=False, default=True, comment="是否启用",
    )
    description = Column(String(256), nullable=True, comment="策略描述")

    def __repr__(self):
        return (
            f"<RetentionPolicy(id={self.id}, target='{self.target_type}', "
            f"days={self.retention_days}, enabled={self.is_enabled})>"
        )
