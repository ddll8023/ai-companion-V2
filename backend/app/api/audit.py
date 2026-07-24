"""审计日志查询 API。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogQueryRequest
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.response import error, success
from app.services import audit as services_audit
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/audit", tags=["审计日志"])


@router.get("/stats", response_model=ApiResponse)
def get_audit_stats(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计日志统计概览。"""
    try:
        total = db.scalar(select(func.count()).select_from(AuditLog))
        success_count = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.result == 0)
        )
        fail_count = db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.result == 1)
        )

        # 按操作类型分组统计
        rows = db.execute(
            select(AuditLog.action, func.count().label("count"))
            .group_by(AuditLog.action)
            .order_by(func.count().desc())
        ).all()
        by_action = [{"action": row.action, "count": row.count} for row in rows]

        return success(data={
            "total": total or 0,
            "success": success_count or 0,
            "fail": fail_count or 0,
            "by_action": by_action,
        })
    except Exception as e:
        return error(code=500, message=f"查询审计统计失败: {e}")


@router.get("/actions", response_model=ApiResponse)
def get_audit_actions(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计操作类型列表。"""
    try:
        rows = db.execute(
            select(AuditLog.action).distinct().order_by(AuditLog.action)
        ).scalars().all()
        return success(data=rows)
    except Exception as e:
        return error(code=500, message=f"查询操作类型失败: {e}")


@router.get("/target-types", response_model=ApiResponse)
def get_audit_target_types(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计对象类型列表。"""
    try:
        rows = db.execute(
            select(AuditLog.target_type).distinct().order_by(AuditLog.target_type)
        ).scalars().all()
        return success(data=[r for r in rows if r is not None])
    except Exception as e:
        return error(code=500, message=f"查询对象类型失败: {e}")


@router.post("/list", response_model=ApiResponse[PaginatedResponse])
def query_audit_logs(
    body: AuditLogQueryRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """查询审计日志列表（POST 方法）。"""
    try:
        result = services_audit.query_audit_logs(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/list", response_model=ApiResponse[PaginatedResponse])
def query_audit_logs_get(
    db: Annotated[Session, Depends(get_db)],
    action: str | None = Query(None, description="操作类型"),
    target_type: str | None = Query(None, description="操作对象类型"),
    result: int | None = Query(None, description="操作结果"),
    start_time: datetime | None = Query(None, description="开始时间"),
    end_time: datetime | None = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """查询审计日志列表（GET 方法，REST 惯例）。"""
    try:
        body = AuditLogQueryRequest(
            action=action,
            target_type=target_type,
            result=result,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )
        result = services_audit.query_audit_logs(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
