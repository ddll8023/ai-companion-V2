"""系统状态和审计查询 API 路由。"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogQueryRequest
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.response import error, success
from app.services import audit as services_audit
from app.services import system as services_system
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/system", tags=["系统状态"])

# ── 全局状态标记（由 main.py 导入设置） ─────────────────────────────
_db_ready: bool = False
_db_migration_completed: bool = False


def set_db_ready(val: bool):
    """设置数据库就绪状态。"""
    global _db_ready
    _db_ready = val


def set_db_migration_completed(val: bool):
    """设置数据库迁移完成状态。"""
    global _db_migration_completed
    _db_migration_completed = val


@router.get("/status", response_model=ApiResponse)
def get_system_status(
    db: Annotated[Session, Depends(get_db)],
):
    """获取聚合系统状态。"""
    try:
        result = services_system.get_system_status(
            db=db,
            db_ready=_db_ready,
            db_migration_completed=_db_migration_completed,
        )
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
    except Exception as exc:
        logger.error(f"获取系统状态失败: {exc}", exc_info=True)
        return error(message="获取系统状态失败")


# ── 审计日志查询 ─────────────────────────────────────────────────────


@router.post("/audit/list", response_model=ApiResponse[PaginatedResponse])
def query_audit_logs(
    body: AuditLogQueryRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """查询审计日志列表。"""
    try:
        result = services_audit.query_audit_logs(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/audit/list", response_model=ApiResponse[PaginatedResponse])
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
    """查询审计日志列表（GET 方法）。"""
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


@router.get("/audit/actions", response_model=ApiResponse)
def get_audit_actions(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计日志中出现的所有操作类型。"""
    try:
        results = db.scalars(
            select(distinct(AuditLog.action))
            .order_by(AuditLog.action)
        ).all()
        return success(data=[r for r in results if r])
    except Exception as exc:
        logger.error(f"获取审计操作类型失败: {exc}")
        return error(message="获取审计操作类型失败")


@router.get("/audit/target-types", response_model=ApiResponse)
def get_audit_target_types(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计日志中出现的所有对象类型。"""
    try:
        results = db.scalars(
            select(distinct(AuditLog.target_type))
            .order_by(AuditLog.target_type)
        ).all()
        return success(data=[r for r in results if r])
    except Exception as exc:
        logger.error(f"获取审计对象类型失败: {exc}")
        return error(message="获取审计对象类型失败")


@router.get("/audit/stats", response_model=ApiResponse)
def get_audit_stats(
    db: Annotated[Session, Depends(get_db)],
):
    """获取审计日志统计。"""
    try:
        total = db.scalar(select(func.count(AuditLog.id)))
        success_count = db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.result == 0)
        )
        fail_count = db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.result == 1)
        )

        # 按操作类型分组
        action_counts = db.execute(
            select(AuditLog.action, func.count(AuditLog.id).label("count"))
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
            .limit(20)
        ).all()

        return success(data={
            "total": total or 0,
            "success": success_count or 0,
            "fail": fail_count or 0,
            "by_action": [
                {"action": row.action, "count": row.count}
                for row in action_counts
            ],
        })
    except Exception as exc:
        logger.error(f"获取审计统计失败: {exc}")
        return error(message="获取审计统计失败")
