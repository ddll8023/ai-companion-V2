"""审计日志查询 API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
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
    """查询审计日志列表。"""
    try:
        result = services_audit.query_audit_logs(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
