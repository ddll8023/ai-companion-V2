"""审计日志记录服务。"""

from __future__ import annotations

from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse, AuditLogQueryRequest
from app.schemas.common import PaginatedResponse, PaginationInfo
from app.core.database import commit_or_rollback
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


def record_audit(
    db: Session,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    summary: str | None = None,
    detail: str | None = None,
    result: int = 0,
) -> AuditLog:
    """记录一条审计日志。

    Args:
        db: 数据库会话
        action: 操作类型
        target_type: 操作对象类型
        target_id: 操作对象 ID
        summary: 操作摘要（不含敏感正文）
        detail: 补充信息（JSON 字符串，不含敏感正文）
        result: 操作结果，0=成功，1=失败
    """
    log = AuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        detail=detail,
        result=result,
    )
    db.add(log)
    commit_or_rollback(db)
    logger.info(f"审计记录: action={action} target_type={target_type} target_id={target_id} result={result}")
    return log


def query_audit_logs(db: Session, query: AuditLogQueryRequest):
    """查询审计日志列表。"""
    base_stmt = select(AuditLog)

    if query.action:
        base_stmt = base_stmt.where(AuditLog.action == query.action)
    if query.target_type:
        base_stmt = base_stmt.where(AuditLog.target_type == query.target_type)
    if query.result is not None:
        base_stmt = base_stmt.where(AuditLog.result == query.result)
    if query.start_time:
        base_stmt = base_stmt.where(AuditLog.created_at >= query.start_time)
    if query.end_time:
        base_stmt = base_stmt.where(AuditLog.created_at <= query.end_time)

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(AuditLog.created_at))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    import math

    return PaginatedResponse(
        lists=[AuditLogResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=math.ceil(total / query.page_size) if total else 0,
        ),
    )
