"""记忆 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── 记忆 Schema ─────────────────────────────────────────────────────────────


class MemoryCreate(BaseModel):
    """创建记忆请求（后台任务使用）。"""

    content: str = Field(..., min_length=1, max_length=10000, description="记忆正文")
    type: str = Field("fact", description="记忆类型: fact/preference/event/goal/habit")
    importance: int = Field(0, ge=0, le=10, description="重要性 0-10")
    session_id: int | None = Field(None, description="来源会话 ID")
    source_version: str | None = Field(None, description="来源内容版本号")
    source_type: str = Field("message", description="来源类型: message/activity/user")
    source_ids: list[int] = Field(default_factory=list, description="来源记录 ID 列表")


class MemoryCorrect(BaseModel):
    """纠正记忆请求。"""

    content: str = Field(..., min_length=1, max_length=10000, description="纠正后的记忆正文")
    type: str = Field("fact", description="记忆类型")
    importance: int = Field(0, ge=0, le=10, description="重要性 0-10")


class MemoryResponse(BaseModel):
    """记忆响应。"""

    id: int
    content: str
    type: str
    importance: int
    status: str
    session_id: int | None = None
    source_version: str | None = None
    version: int
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MemorySourceResponse(BaseModel):
    """记忆来源响应。"""

    id: int
    memory_id: int
    source_type: str
    source_id: int
    content_preview: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryRevisionResponse(BaseModel):
    """记忆修订历史响应。"""

    id: int
    memory_id: int
    previous_content: str
    previous_type: str | None = None
    previous_importance: int | None = None
    changed_by: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MemoryDetailResponse(BaseModel):
    """记忆详情响应（含来源和修订历史）。"""

    memory: MemoryResponse
    sources: list[MemorySourceResponse] = Field(default_factory=list)
    revisions: list[MemoryRevisionResponse] = Field(default_factory=list)


class MemoryListQuery(BaseModel):
    """记忆列表查询参数。"""

    status: str | None = Field(None, description="按状态筛选")
    type: str | None = Field(None, description="按类型筛选")
    session_id: int | None = Field(None, description="按来源会话筛选")
    keyword: str | None = Field(None, description="关键词搜索（FTS5）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")
