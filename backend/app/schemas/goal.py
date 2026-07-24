"""目标和任务 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field


# ========== 枚举（Enums）==========


class GoalStatus(IntEnum):
    """目标状态。"""

    ACTIVE = 0
    COMPLETED = 1
    ABANDONED = 2


class TaskStatus(IntEnum):
    """任务状态。"""

    PENDING = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    ABANDONED = 3


class TaskPriority(IntEnum):
    """任务优先级。"""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class SuggestionStatus(IntEnum):
    """建议状态。"""

    NONE = 0
    PENDING = 1
    ACCEPTED = 2
    REJECTED = 3


# ========== 请求类（Request）==========


class GoalCreate(BaseModel):
    """创建目标请求。"""

    title: str = Field(..., min_length=1, max_length=256, description="目标标题")
    description: str | None = Field(None, max_length=10000, description="目标描述")
    target_date: datetime | None = Field(None, description="目标完成日期")


class GoalUpdate(BaseModel):
    """更新目标请求。"""

    title: str | None = Field(None, min_length=1, max_length=256, description="目标标题")
    description: str | None = Field(None, max_length=10000, description="目标描述")
    status: int | None = Field(None, ge=0, le=2, description="状态: 0=进行中, 1=已完成, 2=已放弃")
    target_date: datetime | None = Field(None, description="目标完成日期")


class GoalListQuery(BaseModel):
    """目标列表查询参数。"""

    status: int | None = Field(None, ge=0, le=2, description="按状态筛选")
    keyword: str | None = Field(None, max_length=256, description="关键词搜索")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class TaskCreate(BaseModel):
    """创建任务请求。"""

    goal_id: int | None = Field(None, description="关联目标 ID")
    title: str = Field(..., min_length=1, max_length=256, description="任务标题")
    description: str | None = Field(None, max_length=10000, description="任务描述")
    priority: int = Field(0, ge=0, le=4, description="优先级: 0=无, 1=低, 2=中, 3=高, 4=紧急")


class TaskUpdate(BaseModel):
    """更新任务请求。"""

    title: str | None = Field(None, min_length=1, max_length=256, description="任务标题")
    description: str | None = Field(None, max_length=10000, description="任务描述")
    status: int | None = Field(None, ge=0, le=3, description="状态: 0=待处理, 1=进行中, 2=已完成, 3=已放弃")
    priority: int | None = Field(None, ge=0, le=4, description="优先级: 0=无, 1=低, 2=中, 3=高, 4=紧急")
    goal_id: int | None = Field(None, description="关联目标 ID")


class TaskListQuery(BaseModel):
    """任务列表查询参数。"""

    goal_id: int | None = Field(None, description="按目标筛选")
    status: int | None = Field(None, ge=0, le=3, description="按状态筛选")
    suggestion_status: int | None = Field(None, ge=0, le=3, description="按建议状态筛选")
    is_suggestion: int | None = Field(None, ge=0, le=1, description="是否仅显示建议: 0=否, 1=是")
    keyword: str | None = Field(None, max_length=256, description="关键词搜索")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class TaskSuggestionCreate(BaseModel):
    """创建 AI 建议任务请求。"""

    title: str = Field(..., min_length=1, max_length=256, description="建议任务标题")
    description: str | None = Field(None, max_length=10000, description="建议任务描述")
    priority: int = Field(0, ge=0, le=4, description="建议优先级")
    suggestion_data: str | None = Field(None, max_length=10000, description="建议理由等附加信息")


class GoalDeleteRequest(BaseModel):
    """删除目标请求。"""

    task_action: str = Field(
        "unlink",
        description="关联任务处理方式: unlink=解除关联, cascade=级联删除",
    )


# ========== 响应类（Response）==========


class GoalResponse(BaseModel):
    """目标响应。"""

    id: int
    title: str
    description: str | None = None
    status: int
    target_date: datetime | None = None
    progress: int = Field(default=0, description="进度百分比 0-100")
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict()


class TaskResponse(BaseModel):
    """任务响应。"""

    id: int
    goal_id: int | None = None
    title: str
    description: str | None = None
    status: int
    priority: int
    is_from_suggestion: int
    suggestion_status: int
    suggestion_data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GoalDetailResponse(BaseModel):
    """目标详情响应（含关联任务列表）。"""

    goal: GoalResponse
    tasks: list[TaskResponse] = Field(default_factory=list)


class TaskWithGoalResponse(BaseModel):
    """任务及其关联目标信息。"""

    id: int
    goal_id: int | None = None
    goal_title: str | None = Field(None, description="关联目标标题")
    title: str
    description: str | None = None
    status: int
    priority: int
    is_from_suggestion: int
    suggestion_status: int
    suggestion_data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
