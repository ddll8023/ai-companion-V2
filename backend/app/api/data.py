"""数据治理 API 路由。

提供数据导出、手动备份和全量清除的 API 入口。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.data_governance import (
    BackupListQuery,
    BackupResponse,
    ClearDataRequest,
    ClearDataResponse,
    DataExportRequest,
    DataExportResponse,
    DataVolumeStats,
    ExportListQuery,
)
from app.schemas.response import error, success
from app.services import data_governance as services_data
from app.utils.exception import ServiceException

router = APIRouter(prefix="/api/v1/data", tags=["数据治理"])


# ── 数据导出 ─────────────────────────────────────────────────────────────────


@router.post("/export", response_model=ApiResponse[DataExportResponse])
def export_data(
    body: DataExportRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """导出用户数据（JSON 格式）。"""
    try:
        result = services_data.export_data(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/exports/list", response_model=ApiResponse[PaginatedResponse[DataExportResponse]])
def list_exports(
    body: ExportListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询导出记录列表。"""
    try:
        result = services_data.list_exports(db, body.page, body.page_size)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/exports/{export_id}", response_model=ApiResponse[None])
def delete_export(
    export_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除导出记录和文件。"""
    try:
        services_data.delete_export(db, export_id)
        return success(message="导出记录已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 手动备份 ─────────────────────────────────────────────────────────────────


@router.post("/backup", response_model=ApiResponse[BackupResponse])
def create_backup(
    db: Annotated[Session, Depends(get_db)],
):
    """创建手动数据库备份。"""
    try:
        result = services_data.create_backup(db)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/backups/list", response_model=ApiResponse[PaginatedResponse[BackupResponse]])
def list_backups(
    body: BackupListQuery,
    db: Annotated[Session, Depends(get_db)],
):
    """查询备份记录列表。"""
    try:
        result = services_data.list_backups(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/backups/{backup_id}", response_model=ApiResponse[None])
def delete_backup(
    backup_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除备份记录和文件。"""
    try:
        services_data.delete_backup(db, backup_id)
        return success(message="备份记录已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 清除全部数据 ──────────────────────────────────────────────────────────────


@router.post("/clear", response_model=ApiResponse[ClearDataResponse])
def clear_all_data(
    body: ClearDataRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """清除全部本地数据（不可逆操作）。"""
    try:
        result = services_data.clear_all_data(db, body)
        return success(data=result, message="全部数据已清除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


# ── 数据量统计 ────────────────────────────────────────────────────────────────


@router.get("/volume", response_model=ApiResponse[DataVolumeStats])
def get_data_volume(
    db: Annotated[Session, Depends(get_db)],
):
    """获取各类型数据量统计。"""
    try:
        result = services_data.get_data_volume_stats(db)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)
