"""数据治理服务。

职责：
- 跨模块统一级联删除
- 数据导出（JSON 格式，含元数据）
- 手动数据库备份
- 清除全部数据（工厂重置）
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
from datetime import datetime

from sqlalchemy import desc, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import commit_or_rollback
from app.models.activity import Activity, PrivacyRule
from app.models.audit import AuditLog
from app.models.chat import ChatSession, Message
from app.models.conversation import AiArtifact, ConversationTurn, SessionSummary
from app.models.data_governance import BackupRecord, DataExport
from app.models.memory import Memory, MemoryReference, MemoryRevision, MemorySource
from app.models.persona import Insight, InsightEvidence, InsightRevision, Observation, PersonaDocument, PersonaState
from app.models.system import ModelConfig
from app.models.task import BackgroundTask
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.data_governance import (
    BackupListQuery,
    BackupResponse,
    ClearDataRequest,
    ClearDataResponse,
    DataExportRequest,
    DataExportResponse,
    DataVolumeStats,
)
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 导出文件的默认最大保留数量
_MAX_EXPORT_RETENTION = 10


# ═══════════════════════════════════════════════════════════════════════════════
# 数据导出
# ═══════════════════════════════════════════════════════════════════════════════


def export_data(
    db: Session,
    request: DataExportRequest,
) -> DataExportResponse:
    """导出用户数据。

    将指定范围的数据导出为 JSON 文件，包含元数据。
    导出文件存储在数据目录的 exports/ 子目录下。

    Args:
        db: 数据库会话
        request: 导出请求参数

    Returns:
        导出记录响应
    """
    data_dir = settings.resolved_data_dir
    export_dir = os.path.join(data_dir, "exports")
    os.makedirs(export_dir, exist_ok=True)

    # 确定导出范围
    scope_modules = request.scope or [
        "sessions", "messages",
        "conversation_turns", "session_summaries", "ai_artifacts",
        "memories", "memory_sources", "memory_revisions", "memory_references",
        "activities",
        "observations", "insights", "insight_evidence", "insight_revisions", "persona_states", "persona_documents",
        "privacy_rules",
    ]

    # 收集数据
    exported_data = {
        "meta": {
            "exported_at": datetime.now().isoformat(),
            "export_type": request.export_type,
            "scope": scope_modules,
            "ai_companion_version": "0.1.0",
        },
        "data": {},
    }

    total_records = 0

    # 逐模块导出（使用流式写入避免大内存占用量，当前数据量可控）
    for module_name in scope_modules:
        records = _export_module(db, module_name, request)
        if records is not None:
            exported_data["data"][module_name] = records
            total_records += len(records)
        else:
            logger.warning(f"导出跳过未知模块: {module_name}")

    # 写入文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(export_dir, f"export_{timestamp}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(exported_data, f, ensure_ascii=False, indent=2, default=str)

    file_size = os.path.getsize(file_path)

    # 保存导出记录
    export_record = DataExport(
        export_type=request.export_type,
        scope=json.dumps(scope_modules, ensure_ascii=False) if request.export_type == "partial" else None,
        start_time=request.start_time,
        end_time=request.end_time,
        status="completed",
        file_path=file_path,
        file_size_bytes=file_size,
        record_count=total_records,
    )
    db.add(export_record)
    commit_or_rollback(db)

    record_audit(
        db=db,
        action="data.export",
        target_type="data_export",
        target_id=export_record.id,
        summary=f"导出数据: type={request.export_type}, records={total_records}, size={file_size}",
        detail=json.dumps({"scope": scope_modules, "file": file_path}),
    )

    logger.info(
        f"数据导出完成: id={export_record.id}, "
        f"records={total_records}, file={file_path}"
    )

    # 清理旧导出文件（保留最近 _MAX_EXPORT_RETENTION 个）
    _cleanup_old_exports(db, export_dir)

    return DataExportResponse.model_validate(export_record)


def _export_module(
    db: Session,
    module_name: str,
    request: DataExportRequest,
) -> list[dict] | None:
    """导出单个模块的数据。

    Args:
        db: 数据库会话
        module_name: 模块名称
        request: 导出请求参数

    Returns:
        数据列表，未知模块返回 None
    """
    # 构建时间过滤条件
    time_conditions = []
    if request.start_time:
        time_conditions.append(lambda c: c.created_at >= request.start_time)
    if request.end_time:
        time_conditions.append(lambda c: c.created_at <= request.end_time)

    module_map = {
        "sessions": lambda: _query_all_as_dicts(db, ChatSession, time_conditions),
        "messages": lambda: _query_all_as_dicts(db, Message, time_conditions),
        "conversation_turns": lambda: _query_all_as_dicts(db, ConversationTurn, time_conditions),
        "session_summaries": lambda: _query_all_as_dicts(db, SessionSummary, time_conditions),
        "ai_artifacts": lambda: _query_all_as_dicts(db, AiArtifact, time_conditions),
        "memories": lambda: _query_all_as_dicts(db, Memory, time_conditions),
        "memory_sources": lambda: _query_all_as_dicts(db, MemorySource, time_conditions),
        "memory_revisions": lambda: _query_all_as_dicts(db, MemoryRevision, time_conditions),
        "memory_references": lambda: _query_all_as_dicts(db, MemoryReference, time_conditions),
        "activities": lambda: _query_all_as_dicts(db, Activity, time_conditions),
        "observations": lambda: _query_all_as_dicts(db, Observation, time_conditions),
        "insights": lambda: _query_all_as_dicts(db, Insight, time_conditions),
        "insight_evidence": lambda: _query_all_as_dicts(db, InsightEvidence, time_conditions),
        "insight_revisions": lambda: _query_all_as_dicts(db, InsightRevision, time_conditions),
        "persona_states": lambda: _query_all_as_dicts(db, PersonaState, time_conditions),
        "persona_documents": lambda: _query_all_as_dicts(db, PersonaDocument, time_conditions),
        "privacy_rules": lambda: _query_all_as_dicts(db, PrivacyRule, time_conditions),
    }

    handler = module_map.get(module_name)
    if handler is None:
        return None

    raw_records = handler()

    # 转换为可 JSON 序列化的格式
    result = []
    for record in raw_records:
        row = {}
        for column in record.__table__.columns:
            value = getattr(record, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            row[column.name] = value
        result.append(row)

    return result


def _query_all_as_dicts(db: Session, model_class, time_conditions: list) -> list:
    """查询模型的所有记录，应用时间条件（如果有 created_at 字段）。"""
    stmt = select(model_class)

    # 只对包含 created_at 的表应用时间过滤
    if hasattr(model_class, "created_at") and time_conditions:
        from sqlalchemy import and_
        conds = [c(model_class.created_at) for c in time_conditions]
        stmt = stmt.where(and_(*conds))

    stmt = stmt.order_by(model_class.id)
    return list(db.scalars(stmt).all())


def _cleanup_old_exports(db: Session, export_dir: str) -> None:
    """清理超出保留数量的旧导出文件。

    Args:
        db: 数据库会话
        export_dir: 导出目录
    """
    try:
        records = (
            db.scalars(
                select(DataExport)
                .order_by(desc(DataExport.id))
            ).all()
        )

        if len(records) <= _MAX_EXPORT_RETENTION:
            return

        to_delete = records[_MAX_EXPORT_RETENTION:]
        for record in to_delete:
            try:
                if os.path.exists(record.file_path):
                    os.remove(record.file_path)
                    logger.debug(f"删除旧导出文件: {record.file_path}")
            except OSError as exc:
                logger.warning(f"删除旧导出文件失败: {record.file_path}, {exc}")

            db.delete(record)

        commit_or_rollback(db)
        logger.info(
            f"旧导出文件清理: deleted={len(to_delete)}, "
            f"keep={_MAX_EXPORT_RETENTION}"
        )
    except Exception as exc:
        logger.warning(f"旧导出文件清理失败（不影响主操作）: {exc}")


def list_exports(
    db: Session,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedResponse[DataExportResponse]:
    """查询导出记录列表。"""
    stmt = select(DataExport).order_by(desc(DataExport.id))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    items = (
        db.scalars(
            stmt.offset((page - 1) * page_size).limit(page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[DataExportResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / page_size),
        ),
    )


def delete_export(db: Session, export_id: int) -> None:
    """删除导出记录及其文件。"""
    export = _get_export_or_error(db, export_id)

    # 先删除数据库记录（确保记录被删除后再清理文件）
    record_audit(
        db=db,
        action="data.export.delete",
        target_type="data_export",
        target_id=export_id,
        summary=f"删除导出记录: id={export_id}",
    )

    db.delete(export)
    commit_or_rollback(db)
    logger.info(f"删除导出记录: id={export_id}")

    # 确认记录已删除后，再删除物理文件
    try:
        if os.path.exists(export.file_path):
            os.remove(export.file_path)
            logger.debug(f"删除导出文件: {export.file_path}")
    except OSError as exc:
        logger.warning(f"删除导出文件失败（数据库记录已清理）: {export.file_path}, {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# 手动备份
# ═══════════════════════════════════════════════════════════════════════════════


def create_backup(db: Session) -> BackupResponse:
    """创建手动数据库备份。

    使用 SQLite 在线备份 API（sqlite3.backup）保证一致性快照，
    不阻塞主数据库连接的其他写入操作。
    """
    data_dir = settings.resolved_data_dir
    backup_dir = os.path.join(data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    db_file = settings.db_file_path
    if not os.path.exists(db_file):
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, "数据库文件不存在")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.db")

    try:
        # 使用 SQLite 备份 API 创建一致性快照
        # 与 VACUUM + shutil.copy2 不同，此方案：
        # 1. 不要求排它锁，备份期间其他连接仍可写入
        # 2. 保证快照一致性（不会出现部分写入的数据）
        source_conn = sqlite3.connect(db_file)
        dest_conn = sqlite3.connect(backup_file)
        try:
            source_conn.backup(dest_conn, pages=4096)
        finally:
            source_conn.close()
            dest_conn.close()
    except Exception as exc:
        raise ServiceException(
            ErrorCode.INTERNAL_ERROR, f"备份文件创建失败: {exc}",
        ) from exc

    file_size = os.path.getsize(backup_file)

    backup_record = BackupRecord(
        file_path=backup_file,
        file_size_bytes=file_size,
        status="completed",
    )
    db.add(backup_record)
    commit_or_rollback(db)

    record_audit(
        db=db,
        action="data.backup.create",
        target_type="backup_record",
        target_id=backup_record.id,
        summary=f"创建手动备份: size={file_size}",
        detail=json.dumps({"file": backup_file}),
    )

    logger.info(f"手动备份创建成功: id={backup_record.id}, file={backup_file}")
    return BackupResponse.model_validate(backup_record)


def list_backups(
    db: Session,
    query: BackupListQuery,
) -> PaginatedResponse[BackupResponse]:
    """查询备份记录列表。"""
    stmt = select(BackupRecord).order_by(desc(BackupRecord.id))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    items = (
        db.scalars(
            stmt
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[BackupResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def delete_backup(db: Session, backup_id: int) -> None:
    """删除备份记录及其文件。"""
    backup = _get_backup_or_error(db, backup_id)

    # 先删除数据库记录（确保记录被删除后再清理文件）
    record_audit(
        db=db,
        action="data.backup.delete",
        target_type="backup_record",
        target_id=backup_id,
        summary=f"删除备份记录: id={backup_id}",
    )

    db.delete(backup)
    commit_or_rollback(db)
    logger.info(f"删除备份记录: id={backup_id}")

    # 确认记录已删除后，再删除物理文件
    try:
        if os.path.exists(backup.file_path):
            os.remove(backup.file_path)
            logger.debug(f"删除备份文件: {backup.file_path}")
    except OSError as exc:
        logger.warning(f"删除备份文件失败（数据库记录已清理）: {backup.file_path}, {exc}")


# ═══════════════════════════════════════════════════════════════════════════════
# 清除全部数据（工厂重置）
# ═══════════════════════════════════════════════════════════════════════════════


def clear_all_data(
    db: Session,
    request: ClearDataRequest,
) -> ClearDataResponse:
    """清除全部本地数据。

    此操作不可逆！执行前需要传入确认密钥 'CLEAR ALL DATA'。

    Args:
        db: 数据库会话
        request: 清除请求（含确认密钥）

    Returns:
        清除结果
    """
    if request.confirm_key != "CLEAR ALL DATA":
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            "确认密钥不正确。如需清除全部数据，请传入 confirm_key='CLEAR ALL DATA'",
        )

    # 记录审计（在清除前执行）
    record_audit(
        db=db,
        action="data.clear_all",
        target_type="system",
        summary="清除全部本地数据（不可逆操作）",
    )

    cleared_tables = []

    # 按依赖顺序清除各表
    # 1. 先清除有外键依赖的表
    for table in [AiArtifact, SessionSummary, ConversationTurn]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    for table in [MemoryReference, MemoryRevision, MemorySource]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    for table in [InsightEvidence, InsightRevision]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    for table in [Message]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    # 2. 清除主表
    main_tables = [
        Memory, Observation, Insight, PersonaState, PersonaDocument, ChatSession, Activity, BackgroundTask,
        AuditLog, ModelConfig, PrivacyRule, DataExport, BackupRecord,
    ]

    for table in main_tables:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    # 3. 清除 FTS5 索引
    try:
        db.execute(text("DELETE FROM memories_fts"))
        cleared_tables.append("memories_fts")
    except Exception as exc:
        logger.warning(f"FTS5 索引清除失败: {exc}")

    commit_or_rollback(db)

    # 检查是否有备份和导出文件需要清理
    data_dir = settings.resolved_data_dir
    cleared_backups = False
    cleared_exports = False

    backup_dir = os.path.join(data_dir, "backups")
    if os.path.exists(backup_dir):
        try:
            shutil.rmtree(backup_dir)
            os.makedirs(backup_dir)
            cleared_backups = True
        except OSError as exc:
            logger.warning(f"备份目录清理失败: {exc}")

    export_dir = os.path.join(data_dir, "exports")
    if os.path.exists(export_dir):
        try:
            shutil.rmtree(export_dir)
            os.makedirs(export_dir)
            cleared_exports = True
        except OSError as exc:
            logger.warning(f"导出目录清理失败: {exc}")

    logger.warning(
        f"全部数据已清除: tables={cleared_tables}, "
        f"backups={cleared_backups}, exports={cleared_exports}"
    )

    return ClearDataResponse(
        cleared_tables=cleared_tables,
        cleared_backups=cleared_backups,
        cleared_exports=cleared_exports,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 数据量统计
# ═══════════════════════════════════════════════════════════════════════════════


def get_data_volume_stats(db: Session) -> DataVolumeStats:
    """获取各类型数据量统计。"""
    model_counts = {
        "sessions": lambda: db.scalar(select(func.count(ChatSession.id))) or 0,
        "messages": lambda: db.scalar(select(func.count(Message.id))) or 0,
        "memories": lambda: db.scalar(select(func.count(Memory.id))) or 0,
        "memory_sources": lambda: db.scalar(select(func.count(MemorySource.id))) or 0,
        "memory_revisions": lambda: db.scalar(select(func.count(MemoryRevision.id))) or 0,
        "memory_references": lambda: db.scalar(select(func.count(MemoryReference.id))) or 0,
        "activities": lambda: db.scalar(select(func.count(Activity.id))) or 0,
        "privacy_rules": lambda: db.scalar(select(func.count(PrivacyRule.id))) or 0,
        "observations": lambda: db.scalar(select(func.count(Observation.id))) or 0,
        "insights": lambda: db.scalar(select(func.count(Insight.id))) or 0,
        "insight_evidence": lambda: db.scalar(select(func.count(InsightEvidence.id))) or 0,
        "insight_revisions": lambda: db.scalar(select(func.count(InsightRevision.id))) or 0,
        "persona_states": lambda: db.scalar(select(func.count(PersonaState.id))) or 0,
        "persona_documents": lambda: db.scalar(select(func.count(PersonaDocument.id))) or 0,
        "audit_logs": lambda: db.scalar(select(func.count(AuditLog.id))) or 0,
        "background_tasks": lambda: db.scalar(select(func.count(BackgroundTask.id))) or 0,
        "model_configs": lambda: db.scalar(select(func.count(ModelConfig.id))) or 0,
        "data_exports": lambda: db.scalar(select(func.count(DataExport.id))) or 0,
        "backup_records": lambda: db.scalar(select(func.count(BackupRecord.id))) or 0,
    }

    stats = {}
    for field_name, count_fn in model_counts.items():
        stats[field_name] = count_fn()

    return DataVolumeStats(**stats)


# ═══════════════════════════════════════════════════════════════════════════════
# 内部方法
# ═══════════════════════════════════════════════════════════════════════════════


def _get_export_or_error(db: Session, export_id: int) -> DataExport:
    """获取导出记录，不存在时抛出异常。"""
    export = db.get(DataExport, export_id)
    if export is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"导出记录不存在: {export_id}")
    return export


def _get_backup_or_error(db: Session, backup_id: int) -> BackupRecord:
    """获取备份记录，不存在时抛出异常。"""
    backup = db.get(BackupRecord, backup_id)
    if backup is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"备份记录不存在: {backup_id}")
    return backup
