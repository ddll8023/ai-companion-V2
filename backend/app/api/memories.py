"""记忆 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse, ErrorCode, PaginatedResponse
from app.schemas.memory import (
    MemoryCorrect,
    MemoryCreate,
    MemoryDetailResponse,
    MemoryListQuery,
    MemoryResponse,
)
from app.schemas.response import error, success
from app.services import memory as services_memory
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/memories", tags=["记忆"])


# ── 记忆 CRUD ──────────────────────────────────────────────────────────────


@router.post("", response_model=ApiResponse[MemoryResponse])
def create_memory(
    body: MemoryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建候选记忆（手动创建）。"""
    try:
        result = services_memory.create_candidate_memory(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/list", response_model=ApiResponse[PaginatedResponse[MemoryResponse]])
def list_memories(
    body: MemoryListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询记忆列表（支持按状态、类型、会话、关键词筛选）。"""
    try:
        result = services_memory.query_memories(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/{memory_id}", response_model=ApiResponse[MemoryDetailResponse])
def get_memory(
    memory_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单个记忆详情（含来源和修订历史）。"""
    try:
        result = services_memory.get_memory(db, memory_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 记忆状态操作 ────────────────────────────────────────────────────────────


@router.post("/{memory_id}/confirm", response_model=ApiResponse[MemoryResponse])
def confirm_memory(
    memory_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """确认候选记忆。"""
    try:
        result = services_memory.confirm_memory(db, memory_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/{memory_id}/correct", response_model=ApiResponse[MemoryResponse])
def correct_memory(
    memory_id: int,
    body: MemoryCorrect,
    db: Annotated[Session, Depends(get_db)],
):
    """纠正记忆（用户提交修正内容）。"""
    try:
        result = services_memory.correct_memory(db, memory_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/{memory_id}/reject", response_model=ApiResponse[MemoryResponse])
def reject_memory(
    memory_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """否定候选记忆。"""
    try:
        result = services_memory.reject_memory(db, memory_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/{memory_id}", response_model=ApiResponse[None])
def delete_memory(
    memory_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除记忆（领域删除）。"""
    try:
        services_memory.delete_memory(db, memory_id)
        return success(message="记忆已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)
