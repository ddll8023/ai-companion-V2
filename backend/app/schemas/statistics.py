"""行为统计 Schema。"""

from pydantic import BaseModel, Field


class BehaviorStatsQuery(BaseModel):
    """行为统计查询参数。"""
    days: int = Field(default=7, ge=1, le=365)


class BehaviorStatsResponse(BaseModel):
    """行为统计响应。"""
    active_hours: list[dict] = []
    app_usage: list[dict] = []
    chat_activity: list[dict] = []
