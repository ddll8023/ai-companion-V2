"""审计日志查询 API。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.audit import AuditLogQueryRequest
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.response import error, success
from app.services import audit as services_audit
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/audit", tags=["审计日志"])


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
