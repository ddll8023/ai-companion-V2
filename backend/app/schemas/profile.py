"""画像 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProfileCategory = Literal[
    "communication_preference",
    "work_habit",
    "learning_preference",
    "interest",
    "decision_preference",
    "time_habit",
    "life_habit",
    "long_term_goal",
    "work_pattern",
    "other",
]

PROFILE_CATEGORIES: list[str] = [
    "communication_preference",
    "work_habit",
    "learning_preference",
    "interest",
    "decision_preference",
    "time_habit",
    "life_habit",
    "long_term_goal",
    "work_pattern",
    "other",
]


# ========== 辅助类（Support）==========


class ProfileSourceResponse(BaseModel):
    """画像来源响应。"""

    id: int = Field(..., description="主键 ID")
    profile_id: int = Field(..., description="关联画像 ID")
    source_type: str = Field(..., description="来源类型: memory/activity/user/extraction")
    memory_id: int | None = Field(None, description="来源记忆 ID")
    content_preview: str | None = Field(None, description="来源内容预览")
    evidence_text: str | None = Field(None, description="提取时的记忆原文证据")
    created_at: datetime | None = Field(None, description="创建时间")

    model_config = ConfigDict(from_attributes=True)


class ProfileRevisionResponse(BaseModel):
    """画像修订历史响应。"""

    id: int = Field(..., description="主键 ID")
    profile_id: int = Field(..., description="关联画像 ID")
    previous_category: str | None = Field(None, description="旧类别")
    previous_content: str = Field(..., description="旧正文")
    previous_confidence: int | None = Field(None, description="旧置信度")
    previous_status: str | None = Field(None, description="旧状态")
    changed_by: str = Field(..., description="变更方: user/system")
    created_at: datetime | None = Field(None, description="创建时间")

    model_config = ConfigDict(from_attributes=True)


# ========== 请求类（Request）==========


class ProfileCreate(BaseModel):
    """创建候选画像请求（后台任务使用）。"""

    category: ProfileCategory = Field("other", description="画像类别")
    content: str = Field(..., min_length=1, max_length=2000, description="画像正文")
    confidence: int = Field(0, ge=0, le=100, description="置信度 0-100")
    is_auto_extracted: int = Field(0, description="是否自动提取: 0=手动, 1=自动")
    memory_ids: list[int] = Field(
        default_factory=list, description="来源记忆 ID 列表",
    )
    evidence_texts: list[str] = Field(
        default_factory=list, description="各条来源对应的记忆原文证据",
    )
    supersedes_profile_id: int | None = Field(
        None, description="候选修订版指向的被修订画像 ID",
    )


class ProfileCorrect(BaseModel):
    """纠正画像请求。"""

    category: ProfileCategory = Field("other", description="纠正后的类别")
    content: str = Field(..., min_length=1, max_length=2000, description="纠正后的正文")
    confidence: int = Field(0, ge=0, le=100, description="纠正后的置信度")


class ProfileListQuery(BaseModel):
    """画像列表查询参数。"""

    category: str | None = Field(None, description="按类别筛选")
    status: str | None = Field(None, description="按状态筛选")
    keyword: str | None = Field(None, description="按正文关键词筛选")
    is_auto_extracted: int | None = Field(None, description="是否自动提取")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页条数")


class BehaviorStatsQuery(BaseModel):
    """行为统计查询参数。"""

    days: int = Field(7, ge=1, le=30, description="统计天数")  # type: ignore[misc]


# ========== 响应类（Response）==========


class ProfileResponse(BaseModel):
    """画像响应。"""

    id: int = Field(..., description="主键 ID")
    category: str = Field(..., description="画像类别")
    content: str = Field(..., description="画像正文")
    confidence: int = Field(..., description="置信度 0-100")
    status: str = Field(..., description="状态")
    is_auto_extracted: int = Field(..., description="是否自动提取")
    version: int = Field(..., description="版本号")
    supersedes_profile_id: int | None = Field(None, description="候选修订版指向的被修订画像 ID")
    error_message: str | None = Field(None, description="错误信息")
    created_at: datetime | None = Field(None, description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    model_config = ConfigDict(from_attributes=True)


class ProfileDetailResponse(BaseModel):
    """画像详情响应（含来源和修订历史）。"""

    profile: ProfileResponse = Field(..., description="画像信息")
    sources: list[ProfileSourceResponse] = Field(
        default_factory=list, description="来源列表",
    )
    revisions: list[ProfileRevisionResponse] = Field(
        default_factory=list, description="修订历史列表",
    )

    model_config = ConfigDict(from_attributes=True)


class BehaviorStatsResponse(BaseModel):
    """行为统计响应。"""

    active_hours: list[dict] = Field(
        default_factory=list,
        description="活跃时段分布: [{\"hour\": 9, \"count\": 23}, ...]",
    )
    app_usage: list[dict] = Field(
        default_factory=list,
        description="应用使用分布: [{\"app_name\": \"Chrome\", \"total_minutes\": 180, \"percentage\": 35}, ...]",
    )
    chat_activity: list[dict] = Field(
        default_factory=list,
        description="用户对话活跃度（仅用户主动发送）: [{\"date\": \"2026-07-16\", \"message_count\": 15}, ...]",
    )

    model_config = ConfigDict(from_attributes=True)
