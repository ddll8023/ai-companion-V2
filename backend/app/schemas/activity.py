"""活动和隐私规则 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


# ── 活动记录 Schema ────────────────────────────────────────────────────────────


class ActivityEvent(BaseModel):
    """活动事件（Electron 上报的原始活动数据）。"""

    app_name: str = Field(..., max_length=256, description="应用名称")
    window_title: str | None = Field(None, max_length=512, description="窗口标题")
    started_at: datetime = Field(..., description="活动开始时间")
    ended_at: datetime | None = Field(None, description="活动结束时间")
    duration_seconds: int | None = Field(None, description="活动持续时长（秒）")
    is_idle: bool = Field(False, description="用户是否空闲")
    platform: str = Field(..., pattern="^(macos|windows)$", description="采集来源平台")
    source_id: str | None = Field(None, max_length=64, description="来源去重标识")


class BatchActivityEvent(BaseModel):
    """批量活动事件上报。"""

    events: list[ActivityEvent] = Field(
        ..., max_length=100, description="活动事件列表（最多 100 条）",
    )


class ActivityResponse(BaseModel):
    """活动记录响应。"""

    id: int
    app_name: str
    window_title: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    is_idle: bool
    platform: str
    privacy_action: str
    masked_app_name: str | None = None
    masked_window_title: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityListQuery(BaseModel):
    """活动记录列表查询参数。"""

    app_name: str | None = Field(None, description="按应用名称筛选")
    platform: str | None = Field(None, pattern="^(macos|windows)?$", description="按平台筛选")
    privacy_action: str | None = Field(None, description="按隐私处理结果筛选")
    keyword: str | None = Field(None, max_length=128, description="关键词搜索（应用名或窗口标题）")
    start_time: datetime | None = Field(None, description="开始时间范围起点")
    end_time: datetime | None = Field(None, description="开始时间范围终点")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class ActivityStats(BaseModel):
    """活动统计响应。"""

    total_count: int = Field(default=0, description="总记录数")
    today_count: int = Field(default=0, description="今日记录数")
    unique_apps: int = Field(default=0, description="今日唯一应用数")


# ── 隐私规则 Schema ────────────────────────────────────────────────────────────


class PrivacyRuleCreate(BaseModel):
    """创建隐私规则请求。"""

    rule_type: str = Field(
        ...,
        pattern="^(global_pause|app_blacklist|app_whitelist|title_keyword|"
        "time_based|content_masking|temp_pause)$",
        description="规则类型",
    )
    rule_value: str = Field(..., max_length=4096, description="规则值")
    description: str | None = Field(None, max_length=256, description="规则描述")
    priority: int = Field(default=0, description="优先级")


class PrivacyRuleUpdate(BaseModel):
    """更新隐私规则请求。"""

    rule_type: str | None = Field(
        None,
        pattern="^(global_pause|app_blacklist|app_whitelist|title_keyword|"
        "time_based|content_masking|temp_pause)?$",
        description="规则类型",
    )
    rule_value: str | None = Field(None, max_length=4096, description="规则值")
    description: str | None = Field(None, max_length=256, description="规则描述")
    is_active: bool | None = Field(None, description="是否启用")
    priority: int | None = Field(None, description="优先级")


class PrivacyRuleResponse(BaseModel):
    """隐私规则响应。"""

    id: int
    rule_type: str
    rule_value: str
    description: str | None = None
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrivacyRuleListQuery(BaseModel):
    """隐私规则列表查询参数。"""

    rule_type: str | None = Field(None, description="按规则类型筛选")
    is_active: bool | None = Field(None, description="按启用状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=50, ge=1, le=100, description="每页条数")


class PrivacyEvaluateRequest(BaseModel):
    """隐私规则评估请求。

    用于 Electron 在发送活动事件前预检查当前场景是否允许采集。
    """

    app_name: str = Field(..., max_length=256, description="应用名称")
    window_title: str | None = Field(None, max_length=512, description="窗口标题")
    platform: str = Field(..., pattern="^(macos|windows)$", description="平台")


class PrivacyEvaluateResult(BaseModel):
    """隐私规则评估结果。"""

    allowed: bool = Field(..., description="是否允许采集")
    action: str = Field(..., description="处理动作: allowed/blocked/masked")
    reason: str | None = Field(None, description="阻断或脱敏原因")
    matched_rule_id: int | None = Field(None, description="匹配的规则 ID")
    masked_app_name: str | None = Field(None, description="脱敏后的应用名称（如适用）")
    masked_window_title: str | None = Field(None, description="脱敏后的窗口标题（如适用）")


# ── 平台能力 Schema ────────────────────────────────────────────────────────────


class PlatformCapability(BaseModel):
    """平台单项能力状态。"""

    name: str = Field(..., description="能力名称")
    status: str = Field(
        ...,
        pattern="^(available|pending_auth|denied|restricted|unsupported|not_implemented)$",
        description="能力状态",
    )
    label: str = Field(..., description="能力显示名称")
    description: str | None = Field(None, description="状态说明")


class PlatformCapabilitiesResponse(BaseModel):
    """平台能力列表响应。"""

    platform: str = Field(..., description="当前平台: macos/windows")
    capabilities: list[PlatformCapability] = Field(
        default_factory=list, description="能力列表",
    )
