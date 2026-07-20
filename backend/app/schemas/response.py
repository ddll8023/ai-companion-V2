"""统一响应 helper。"""

from __future__ import annotations

from typing import TypeVar

from app.schemas.common import ApiResponse, ErrorCode

T = TypeVar("T")


def success(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    """返回成功响应。"""
    return ApiResponse(code=ErrorCode.SUCCESS, message=message, data=data)


def error(
    code: int = ErrorCode.INTERNAL_ERROR,
    message: str = "服务器错误",
    data: T | None = None,
) -> ApiResponse:
    """返回错误响应。"""
    return ApiResponse(code=code, message=message, data=data)
