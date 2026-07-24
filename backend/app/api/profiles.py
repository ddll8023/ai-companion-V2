"""画像 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import api_key_cache
from app.core.database import get_db
from app.schemas.common import ApiResponse, ErrorCode, PaginatedResponse
from app.schemas.profile import (
    ProfileCorrect,
    ProfileCreate,
    ProfileDetailResponse,
    ProfileListQuery,
    ProfileResponse,
)
from app.schemas.response import error, success
from app.services import profile as services_profile
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/profiles", tags=["画像"])


# ── 画像提取 ────────────────────────────────────────────────────────────


@router.post("/extract", response_model=ApiResponse[dict])
def extract_profiles(
    db: Annotated[Session, Depends(get_db)],
):
    """从已确认记忆中提取画像特征（手动触发，同步执行）。

    API Key 从进程内存缓存获取（由 chat 服务在对话时通过 api_key_cache 写入），
    无需前端传递。
    """
    try:
        api_key = api_key_cache.peek_global()
        if not api_key:
            return error(
                code=ErrorCode.PARAM_ERROR,
                message="API Key 不可用（请先进行一次对话）",
            )
        result = services_profile.sync_extract_profiles(db, api_key=api_key)
        return success(data={"result": result})
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 画像 CRUD ────────────────────────────────────────────────────────────


@router.post("", response_model=ApiResponse[ProfileResponse])
def create_profile(
    body: ProfileCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建候选画像。"""
    try:
        result = services_profile.create_candidate_profile(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/list", response_model=ApiResponse[PaginatedResponse[ProfileResponse]])
def list_profiles(
    body: ProfileListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询画像列表（支持按类别、状态、关键词筛选）。"""
    try:
        result = services_profile.query_profiles(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/{profile_id}", response_model=ApiResponse[ProfileDetailResponse])
def get_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单个画像详情（含来源和修订历史）。"""
    try:
        result = services_profile.get_profile(db, profile_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 画像状态操作 ──────────────────────────────────────────────────────────


@router.post("/{profile_id}/confirm", response_model=ApiResponse[ProfileResponse])
def confirm_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """确认候选画像。"""
    try:
        result = services_profile.confirm_profile(db, profile_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/{profile_id}/correct", response_model=ApiResponse[ProfileResponse])
def correct_profile(
    profile_id: int,
    body: ProfileCorrect,
    db: Annotated[Session, Depends(get_db)],
):
    """纠正画像（用户提交修正内容）。"""
    try:
        result = services_profile.correct_profile(db, profile_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/{profile_id}/reject", response_model=ApiResponse[ProfileResponse])
def reject_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """否定画像。"""
    try:
        result = services_profile.reject_profile(db, profile_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/{profile_id}", response_model=ApiResponse[None])
def delete_profile(
    profile_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除画像。"""
    try:
        services_profile.delete_profile(db, profile_id)
        return success(message="画像已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)
