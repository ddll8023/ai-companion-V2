"""统一响应 helper。"""

from __future__ import annotations

from typing import TypeVar

from app.schemas.common import ErrorCode

T = TypeVar("T")


def success(data: T | None = None, message: str = "success") -> dict:
    """返回成功响应。"""
    return {"code": ErrorCode.SUCCESS, "message": message, "data": data}


def error(
    code: int = ErrorCode.INTERNAL_ERROR,
    message: str = "服务器错误",
    data: T | None = None,
) -> dict:
    """返回错误响应。"""
    return {"code": code, "message": message, "data": data}
