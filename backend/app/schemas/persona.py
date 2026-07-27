"""人物理解请求与响应 Schema。"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ObservationResponse(BaseModel):
    """观察响应。"""
    id: int
    observation_type: str
    dimension: str
    content: str
    session_id: int | None = None
    source_message_id: int | None = None
    evidence: str
    reflected_at: datetime | None = None
    is_deleted: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ObservationListQuery(BaseModel):
    """观察列表查询。"""
    dimension: str | None = None
    observation_type: str | None = None
    keyword: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=30, ge=1, le=100)


class InsightResponse(BaseModel):
    """洞见响应。"""
    id: int
    insight_type: str
    dimension: str
    content: str
    abstraction_level: int
    maturity: str
    confidence: int
    stability_score: int
    support_count: int
    contradiction_count: int
    user_override: bool
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InsightListQuery(BaseModel):
    """洞见列表查询。"""
    maturity: str | None = None
    dimension: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class InsightCorrection(BaseModel):
    """用户纠正洞见。"""
    content: str = Field(..., min_length=2, max_length=1000)
    dimension: str | None = Field(default=None, max_length=64)


class PersonaDocumentResponse(BaseModel):
    """人物侧写文档响应。"""
    id: int
    content: str
    structured_sections: dict
    user_edited_sections: dict
    cited_insight_ids: list
    version: int
    is_active: bool
    change_summary: str | None = None
    edited_by: str
    is_pending_review: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PersonaDocumentEdit(BaseModel):
    """用户编辑人物侧写文档。"""
    content: str = Field(..., min_length=1, max_length=20000)
    edited_sections: dict = Field(default_factory=dict)


class PersonaTriggerResponse(BaseModel):
    """人物理解任务触发结果。"""
    task_id: int | None = None
    observations_created: int = 0
    insights_changed: int = 0
    document_compiled: bool = False


class PersonaOverview(BaseModel):
    """人物理解总览。"""
    document: PersonaDocumentResponse | None = None
    insight_count: int = 0
    observation_count: int = 0
    state_count: int = 0
