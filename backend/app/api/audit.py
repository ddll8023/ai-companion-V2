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
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["审计日志"])


@router.get("/stats", response_model=ApiResponse)
def get_audit_stats(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计日志统计概览。"""
    try:
        stats = services_audit.get_audit_stats(db)
        return success(data=stats)
    except Exception as exc:
        logger.exception("查询审计统计失败")
        return error(code=500, message="查询审计统计失败")


@router.get("/actions", response_model=ApiResponse)
def get_audit_actions(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计操作类型列表。"""
    try:
        actions = services_audit.get_audit_actions(db)
        return success(data=actions)
    except Exception as exc:
        logger.exception("查询操作类型失败")
        return error(code=500, message="查询操作类型失败")


@router.get("/target-types", response_model=ApiResponse)
def get_audit_target_types(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计对象类型列表。"""
    try:
        types = services_audit.get_audit_target_types(db)
        return success(data=types)
    except Exception as exc:
        logger.exception("查询对象类型失败")
        return error(code=500, message="查询对象类型失败")


@router.get("/list", response_model=ApiResponse[PaginatedResponse])
def query_audit_logs(
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
    except Exception as exc:
        logger.exception("查询审计日志失败")
        return error(code=500, message="查询审计日志失败")
