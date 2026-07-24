"""审计日志 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """审计日志响应。"""

    id: int
    action: str
    target_type: str | None = None
    target_id: int | None = None
    actor_id: int | None = None
    actor_name: str | None = None
    ip_address: str | None = None
    summary: str | None = None
    detail: str | None = None
    result: int = 0
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogQueryRequest(BaseModel):
    """审计日志查询请求。"""

    action: str | None = None
    target_type: str | None = None
    result: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
