"""后台任务 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    """创建后台任务请求。"""

    task_type: str = Field(..., max_length=64, description="任务类型")
    payload: str | None = Field(None, description="任务参数（JSON 字符串）")
    dedup_key: str | None = Field(None, max_length=128, description="去重键")
    priority: int = Field(0, ge=0, description="优先级，数值越大越优先")
    max_retries: int = Field(3, ge=0, le=10, description="最大重试次数")
    source_version: str | None = Field(None, max_length=64, description="来源内容版本号")
    scheduled_at: datetime | None = Field(None, description="计划执行时间（留空则立即执行）")


class TaskResponse(BaseModel):
    """后台任务响应。"""

    id: int
    task_type: str
    status: str
    payload: str | None = None
    dedup_key: str | None = None
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    source_version: str | None = None
    error_message: str | None = None
    result: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskQueryRequest(BaseModel):
    """任务查询请求。"""

    task_type: str | None = Field(None, max_length=64, description="任务类型过滤")
    status: str | None = Field(None, max_length=16, description="状态过滤")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")
