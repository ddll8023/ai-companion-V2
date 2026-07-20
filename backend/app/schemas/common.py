"""统一响应模型。"""

from __future__ import annotations

from enum import IntEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorCode(IntEnum):
    """全局错误码。"""

    SUCCESS = 0
    PARAM_ERROR = 1001
    DATA_NOT_FOUND = 1002
    NOT_LOGGED_IN = 2001
    TOKEN_EXPIRED = 2002
    PERMISSION_DENIED = 2003
    UNSUPPORTED_FILE_FORMAT = 3001
    FILE_TOO_LARGE = 3002
    AI_SERVICE_ERROR = 4001
    INTERNAL_ERROR = 5001
    PASSWORD_ERROR = 6001


class ApiResponse(BaseModel, Generic[T]):
    """统一业务响应。"""

    code: int = 0
    message: str = "success"
    data: T | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"code": 0, "message": "success", "data": {}}},
    )


class PaginationInfo(BaseModel):
    """分页信息。"""

    page: int = 1
    page_size: int = 10
    total: int = 0
    total_pages: int = 0


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应。"""

    lists: list[T] = Field(default_factory=list)
    pagination: PaginationInfo = Field(default_factory=PaginationInfo)

    model_config = ConfigDict(from_attributes=True)
