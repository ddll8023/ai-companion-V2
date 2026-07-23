"""数据治理 API 路由。

提供数据导出、备份恢复、保留策略管理和全量清除的 API 入口。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import Base, get_db
from app.schemas.common import ApiResponse, ErrorCode, PaginatedResponse
from app.schemas.data_governance import (
    BackupCreateRequest,
    BackupListQuery,
    BackupResponse,
    ClearDataRequest,
    ClearDataResponse,
    DataExportRequest,
    DataExportResponse,
    DataVolumeStats,
    ExportListQuery,
    RestoreRequest,
    RestoreResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
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


# ── 备份与恢复 ────────────────────────────────────────────────────────────────


@router.post("/backup", response_model=ApiResponse[BackupResponse])
def create_backup(
    body: BackupCreateRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """创建数据库备份。"""
    try:
        result = services_data.create_backup(db, body)
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


@router.post("/restore", response_model=ApiResponse[RestoreResponse])
def restore_from_backup(
    body: RestoreRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """从备份恢复数据库。"""
    try:
        result = services_data.restore_from_backup(
            db, body, Base.metadata,
        )
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


# ── 保留策略 ─────────────────────────────────────────────────────────────────


@router.post("/retention", response_model=ApiResponse[RetentionPolicyResponse])
def create_retention_policy(
    body: RetentionPolicyCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """创建保留策略。"""
    try:
        result = services_data.create_retention_policy(db, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/retention", response_model=ApiResponse[list[RetentionPolicyResponse]])
def list_retention_policies(
    db: Annotated[Session, Depends(get_db)],
):
    """查询所有保留策略。"""
    try:
        result = services_data.list_retention_policies(db)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.get("/retention/{policy_id}", response_model=ApiResponse[RetentionPolicyResponse])
def get_retention_policy(
    policy_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """获取单条保留策略。"""
    try:
        result = services_data.get_retention_policy(db, policy_id)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/retention/{policy_id}", response_model=ApiResponse[RetentionPolicyResponse])
def update_retention_policy(
    policy_id: int,
    body: RetentionPolicyUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """更新保留策略。"""
    try:
        result = services_data.update_retention_policy(db, policy_id, body)
        return success(data=result)
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.delete("/retention/{policy_id}", response_model=ApiResponse[None])
def delete_retention_policy(
    policy_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """删除保留策略。"""
    try:
        services_data.delete_retention_policy(db, policy_id)
        return success(message="保留策略已删除")
    except ServiceException as e:
        return error(code=e.code, message=e.message)


@router.post("/retention/cleanup", response_model=ApiResponse[dict])
def run_retention_cleanup(
    db: Annotated[Session, Depends(get_db)],
):
    """手动触发保留策略自动清理。"""
    try:
        result = services_data.run_retention_cleanup(db)
        return success(data=result, message="保留策略清理完成")
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
