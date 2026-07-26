"""数据治理服务。

职责：
- 跨模块统一级联删除
- 数据导出（JSON 格式，含元数据）
- 数据库备份与恢复
- 保留策略管理和自动清理
- 清除全部数据（工厂重置）
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
from datetime import datetime, timedelta

from sqlalchemy import delete, desc, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import commit_or_rollback
from app.models.activity import Activity, PrivacyRule
from app.models.audit import AuditLog
from app.models.chat import ChatSession, Message
from app.models.conversation import AiArtifact, ConversationTurn, SessionSummary
from app.models.data_governance import BackupRecord, DataExport, RetentionPolicy
from app.models.goal import Goal, Task
from app.models.memory import Memory, MemoryReference, MemoryRevision, MemorySource
from app.models.profile import Profile, ProfileRevision, ProfileSource
from app.models.system import ModelConfig
from app.models.task import BackgroundTask
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.data_governance import (
    BackupCreateRequest,
    BackupListQuery,
    BackupResponse,
    ClearDataRequest,
    ClearDataResponse,
    DataExportRequest,
    DataExportResponse,
    DataVolumeStats,
    RestoreRequest,
    RestoreResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
    RetentionPolicyUpdate,
)
from app.services.audit import record_audit
from app.services.embedding import _ensure_model, embed_texts, serialize_embedding
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 导出文件的默认最大保留数量
_MAX_EXPORT_RETENTION = 10
# 自动备份的默认最大保留数量
_MAX_AUTO_BACKUP_RETENTION = 7


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
        "goals", "tasks",
        "profiles", "profile_sources", "profile_revisions",
        "privacy_rules",
        "retention_policies",
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
        "goals": lambda: _query_all_as_dicts(db, Goal, time_conditions),
        "tasks": lambda: _query_all_as_dicts(db, Task, time_conditions),
        "profiles": lambda: _query_all_as_dicts(db, Profile, time_conditions),
        "profile_sources": lambda: _query_all_as_dicts(db, ProfileSource, time_conditions),
        "profile_revisions": lambda: _query_all_as_dicts(db, ProfileRevision, time_conditions),
        "privacy_rules": lambda: _query_all_as_dicts(db, PrivacyRule, time_conditions),
        "retention_policies": lambda: _query_all_as_dicts(db, RetentionPolicy, time_conditions),
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
# 备份与恢复
# ═══════════════════════════════════════════════════════════════════════════════


def create_backup(db: Session, request: BackupCreateRequest) -> BackupResponse:
    """创建数据库备份。

    使用 SQLite 在线备份 API（sqlite3.backup）保证一致性快照，
    不阻塞主数据库连接的其他写入操作。

    Args:
        db: 数据库会话
        request: 备份请求参数

    Returns:
        备份记录响应
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
        backup_type=request.backup_type,
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
        summary=f"创建备份: type={request.backup_type}, size={file_size}",
        detail=json.dumps({"file": backup_file}),
    )

    logger.info(
        f"备份创建成功: id={backup_record.id}, "
        f"type={request.backup_type}, file={backup_file}"
    )

    # 清理旧自动备份
    if request.backup_type == "auto":
        _cleanup_old_auto_backups(db, backup_dir)

    return BackupResponse.model_validate(backup_record)


def _cleanup_old_auto_backups(db: Session, backup_dir: str) -> None:
    """清理超出保留数量的旧自动备份记录和文件。

    Args:
        db: 数据库会话
        backup_dir: 备份目录
    """
    try:
        records = (
            db.scalars(
                select(BackupRecord)
                .where(BackupRecord.backup_type == "auto")
                .order_by(desc(BackupRecord.id))
            ).all()
        )

        if len(records) <= _MAX_AUTO_BACKUP_RETENTION:
            return

        to_delete = records[_MAX_AUTO_BACKUP_RETENTION:]
        for record in to_delete:
            try:
                if os.path.exists(record.file_path):
                    os.remove(record.file_path)
                    logger.debug(f"删除旧备份文件: {record.file_path}")
            except OSError as exc:
                logger.warning(f"删除旧备份文件失败: {record.file_path}, {exc}")

            db.delete(record)

        commit_or_rollback(db)
        logger.info(
            f"旧自动备份清理: deleted={len(to_delete)}, "
            f"keep={_MAX_AUTO_BACKUP_RETENTION}"
        )
    except Exception as exc:
        logger.warning(f"旧自动备份清理失败（不影响主操作）: {exc}")


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


def restore_from_backup(
    db: Session,
    request: RestoreRequest,
    base_metadata,
) -> RestoreResponse:
    """从备份文件恢复数据库。

    恢复流程：
    1. 检查备份文件是否存在
    2. 保护当前数据库（复制到 protected/ 目录）
    3. 关闭当前数据库连接以释放文件锁
    4. 用备份文件替换当前数据库文件
    5. 使用新连接重建 FTS5 索引和表结构
    6. 更新备份记录状态

    Note: 恢复后当前 db session 已关闭，调用方不应再使用此 db 实例。
          FastAPI 的 get_db() 会正确处理 session 关闭。

    Args:
        db: 数据库会话（会被关闭）
        request: 恢复请求参数
        base_metadata: SQLAlchemy Base.metadata

    Returns:
        恢复响应
    """
    backup = _get_backup_or_error(db, request.backup_id)

    if not os.path.exists(backup.file_path):
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"备份文件不存在: {backup.file_path}")

    if backup.status == "restoring":
        raise ServiceException(ErrorCode.PARAM_ERROR, "此备份正在被恢复中")

    db_file = settings.db_file_path
    data_dir = settings.resolved_data_dir

    # 保护原数据库
    protected_dir = os.path.join(data_dir, "protected")
    os.makedirs(protected_dir, exist_ok=True)
    protection_file = os.path.join(
        protected_dir,
        f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
    )

    try:
        # WAL checkpoint 确保所有数据写入主文件
        try:
            db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            db.commit()
        except Exception as exc:
            logger.warning(f"WAL checkpoint 执行失败（可继续）: {exc}")

        shutil.copy2(db_file, protection_file)
        logger.info(f"原数据库已保护: {protection_file}")
    except OSError as exc:
        raise ServiceException(
            ErrorCode.INTERNAL_ERROR, f"原数据库保护失败: {exc}",
        ) from exc

    # 标记备份为恢复中
    backup.status = "restoring"
    commit_or_rollback(db)

    # 关闭当前连接以释放文件锁
    db.close()

    try:
        # 替换数据库文件
        shutil.copy2(backup.file_path, db_file)
        logger.info(f"数据库已从备份恢复: {backup.file_path}")

        logger.info(
            f"数据库已从备份恢复: {backup.file_path}, "
            f"操作审计: data.restore, backup_id={request.backup_id}"
        )

        # 使用新连接重建 FTS5 和更新备份状态
        _rebuild_fts5_after_restore(
            db_file, base_metadata, request.backup_id,
        )

        logger.info(
            f"数据库恢复成功: backup_id={request.backup_id}, "
            f"protected_file={protection_file}"
        )

        return RestoreResponse(
            backup_id=request.backup_id,
            status="restored",
            file_path=backup.file_path,
            message=f"数据库已从备份恢复。原数据库已保护在: {protection_file}",
            restored_at=datetime.now(),
            database_was_recreated=True,
        )

    except Exception as exc:
        # 恢复失败，尝试回滚到保护文件
        logger.error(f"数据库恢复失败，尝试回滚: {exc}")

        try:
            if os.path.exists(db_file):
                shutil.copy2(protection_file, db_file)
                logger.info(f"数据库已回滚到保护版本: {protection_file}")
            _rebuild_fts5_after_restore(
                db_file, base_metadata, request.backup_id,
            )
        except Exception as rollback_exc:
            logger.error(f"数据库回滚失败: {rollback_exc}")

        raise ServiceException(
            ErrorCode.INTERNAL_ERROR, f"数据库恢复失败: {exc}",
        ) from exc


def _rebuild_fts5_after_restore(
    db_file: str,
    base_metadata,
    backup_id: int | None = None,
) -> None:
    """在替换数据库文件后重建 FTS5 索引和更新备份状态。

    使用独立的 sqlite3 连接操作，不依赖 SQLAlchemy session。

    Args:
        db_file: 数据库文件路径
        base_metadata: SQLAlchemy Base.metadata（仅用于表创建）
        backup_id: 备份记录 ID（用于更新备份状态）
    """
    import sqlite3

    conn = sqlite3.connect(db_file)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row

    try:
        # 确保所有业务表存在（幂等，缺失则创建）
        # 使用 SQLAlchemy 引擎创建表结构
        from sqlalchemy import create_engine

        eng = create_engine(f"sqlite:///{db_file}")
        base_metadata.create_all(bind=eng, checkfirst=True)
        eng.dispose()

        # 重建 FTS5
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts "
            "USING fts5(content, memory_id UNINDEXED, type UNINDEXED)"
        )
        conn.execute("DELETE FROM memories_fts")
        conn.execute(
            "INSERT INTO memories_fts (content, memory_id, type) "
            "SELECT content, id, type FROM memories "
            "WHERE status IN ('confirmed', 'corrected')"
        )

        # 创建版本表（如不存在）
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _db_version ("
            "version INTEGER NOT NULL, "
            "updated_at TEXT NOT NULL DEFAULT (datetime('now'))"
            ")"
        )

        # 更新备份记录状态
        if backup_id is not None:
            conn.execute(
                "UPDATE backup_records SET "
                "status = 'restored', restored_at = datetime('now') "
                "WHERE id = ?",
                (backup_id,),
            )

        conn.commit()
        logger.info("恢复完成后 FTS5 索引和表结构已重建")
    except Exception as exc:
        logger.warning(f"恢复后重建失败: {exc}")
        conn.rollback()
    finally:
        conn.close()


def _rebuild_fts5(db: Session, base_metadata) -> None:
    """重建数据库表和 FTS5 索引。

    Args:
        db: 数据库会话
        base_metadata: SQLAlchemy Base.metadata
    """
    try:
        # 从当前数据库引擎获取绑定
        bind = db.get_bind()
        base_metadata.create_all(bind=bind, checkfirst=True)

        # 重建 FTS5 表
        try:
            db.execute(text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts "
                "USING fts5(content, memory_id UNINDEXED, type UNINDEXED)"
            ))
            db.execute(text("DELETE FROM memories_fts"))
            db.execute(text(
                "INSERT INTO memories_fts (content, memory_id, type) "
                "SELECT content, id, type FROM memories "
                "WHERE status IN ('confirmed', 'corrected')"
            ))
            db.commit()

            # 全量重建嵌入向量（非阻塞）
            _rebuild_embeddings_after_reset(db)
        except Exception as fts_exc:
            logger.warning(f"恢复后 FTS5 重建失败（功能可降级）: {fts_exc}")
    except Exception as exc:
        logger.warning(f"恢复后表重建异常: {exc}")


def _rebuild_embeddings_after_reset(db: Session):
    """工厂重置后全量重建嵌入向量。"""
    try:
        if not _ensure_model():
            logger.warning("嵌入模型不可用，跳过向量重建")
            return

        items = db.scalars(
            select(Memory).where(
                Memory.status.in_(["confirmed", "corrected"]),
            )
        ).all()
        if not items:
            return

        texts = [item.content for item in items]
        embeddings = embed_texts(texts)
        updated = 0
        for item, vec in zip(items, embeddings):
            item.embedding = serialize_embedding(vec)
            updated += 1
        db.commit()
        logger.info("嵌入向量已全量重建: %d 条", updated)
    except Exception as exc:
        logger.warning("嵌入向量重建失败（可降级）: %s", exc)
        db.rollback()


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
# 保留策略
# ═══════════════════════════════════════════════════════════════════════════════


def create_retention_policy(
    db: Session,
    data: RetentionPolicyCreate,
) -> RetentionPolicyResponse:
    """创建保留策略。"""
    # 检查是否已存在同目标类型的策略
    existing = db.scalar(
        select(RetentionPolicy).where(RetentionPolicy.target_type == data.target_type)
    )
    if existing is not None:
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"目标类型 '{data.target_type}' 的保留策略已存在，请使用更新接口",
        )

    policy = RetentionPolicy(
        target_type=data.target_type,
        retention_days=data.retention_days,
        is_enabled=1 if data.is_enabled else 0,
        description=data.description,
    )
    db.add(policy)
    commit_or_rollback(db)

    record_audit(
        db=db,
        action="retention_policy.create",
        target_type="retention_policy",
        target_id=policy.id,
        summary=f"创建保留策略: target={data.target_type}, days={data.retention_days}",
    )

    logger.info(
        f"创建保留策略: id={policy.id}, "
        f"target={data.target_type}, days={data.retention_days}"
    )
    return RetentionPolicyResponse.model_validate(policy)


def update_retention_policy(
    db: Session,
    policy_id: int,
    data: RetentionPolicyUpdate,
) -> RetentionPolicyResponse:
    """更新保留策略。"""
    policy = _get_policy_or_error(db, policy_id)

    if data.retention_days is not None:
        policy.retention_days = data.retention_days
    if data.is_enabled is not None:
        policy.is_enabled = 1 if data.is_enabled else 0
    if data.description is not None:
        policy.description = data.description

    commit_or_rollback(db)

    record_audit(
        db=db,
        action="retention_policy.update",
        target_type="retention_policy",
        target_id=policy_id,
        summary=f"更新保留策略: target={policy.target_type}, days={policy.retention_days}",
    )

    return RetentionPolicyResponse.model_validate(policy)


def list_retention_policies(db: Session) -> list[RetentionPolicyResponse]:
    """查询所有保留策略。"""
    policies = db.scalars(
        select(RetentionPolicy).order_by(RetentionPolicy.target_type)
    ).all()
    return [RetentionPolicyResponse.model_validate(p) for p in policies]


def get_retention_policy(db: Session, policy_id: int) -> RetentionPolicyResponse:
    """获取单条保留策略。"""
    return RetentionPolicyResponse.model_validate(_get_policy_or_error(db, policy_id))


def delete_retention_policy(db: Session, policy_id: int) -> None:
    """删除保留策略。"""
    policy = _get_policy_or_error(db, policy_id)

    record_audit(
        db=db,
        action="retention_policy.delete",
        target_type="retention_policy",
        target_id=policy_id,
        summary=f"删除保留策略: target={policy.target_type}",
    )

    db.delete(policy)
    commit_or_rollback(db)
    logger.info(f"删除保留策略: id={policy_id}")


# ── 保留策略自动清理任务 ──────────────────────────────────────────────────────


def run_retention_cleanup(db: Session) -> dict[str, int]:
    """执行保留策略自动清理。

    根据已启用的保留策略，清理过期数据。

    Returns:
        各目标类型的清理数量统计
    """
    policies = db.scalars(
        select(RetentionPolicy)
        .where(RetentionPolicy.is_enabled == 1)
    ).all()

    if not policies:
        logger.info("保留策略清理: 无已启用的策略")
        return {}

    results: dict[str, int] = {}
    cutoff_now = datetime.now()

    for policy in policies:
        cutoff_time = cutoff_now - timedelta(days=policy.retention_days)
        count = _cleanup_target_type(db, policy.target_type, cutoff_time)
        if count > 0:
            results[policy.target_type] = count
            logger.info(
                f"保留策略清理: target={policy.target_type}, "
                f"days={policy.retention_days}, deleted={count}"
            )

    if results:
        record_audit(
            db=db,
            action="retention_policy.cleanup",
            target_type="retention_policy",
            summary=f"保留策略自动清理完成: {json.dumps(results, ensure_ascii=False)}",
            detail=json.dumps(results),
        )

    return results


def _cleanup_target_type(db: Session, target_type: str, cutoff: datetime) -> int:
    """清理指定类型的过期数据。

    Args:
        db: 数据库会话
        target_type: 目标数据类型
        cutoff: 截止时间，比此时间更早的数据将被删除

    Returns:
        删除的记录数
    """
    cleanup_map = {
        "activities": lambda: _cleanup_activities(db, cutoff),
        "messages": lambda: _cleanup_messages(db, cutoff),
        "memories": lambda: _cleanup_memories(db, cutoff),
        "profiles": lambda: _cleanup_model_by_time(db, Profile, cutoff),
        "audit_logs": lambda: _cleanup_model_by_time(db, AuditLog, cutoff),
        "backups": lambda: _cleanup_backups_by_time(db, cutoff),
        "background_tasks": lambda: _cleanup_model_by_time(db, BackgroundTask, cutoff),
        "model_configs": lambda: _cleanup_model_by_time(db, ModelConfig, cutoff),
    }

    handler = cleanup_map.get(target_type)
    if handler is not None:
        return handler()
    logger.warning(f"保留策略清理: 未知目标类型 '{target_type}'，跳过")
    return 0


def _cleanup_model_by_time(db: Session, model_class, cutoff: datetime) -> int:
    """按时间清理模型记录。"""
    if not hasattr(model_class, "created_at"):
        return 0
    stmt = delete(model_class).where(model_class.created_at < cutoff)
    result = db.execute(stmt)
    commit_or_rollback(db)
    return result.rowcount or 0


def _cleanup_messages(db: Session, cutoff: datetime) -> int:
    """按时间清理消息（同时清理关联的记忆来源和画像来源）。"""
    # 先获取要删除的消息 ID
    msg_ids = db.scalars(
        select(Message.id).where(Message.created_at < cutoff)
    ).all()

    if not msg_ids:
        return 0

    # 清理关联的记忆引用
    db.execute(
        delete(MemoryReference).where(MemoryReference.message_id.in_(msg_ids))
    )

    # 清理关联的记忆来源（软引用，无外键约束）
    db.execute(
        delete(MemorySource).where(
            MemorySource.source_type == "message",
            MemorySource.source_id.in_(msg_ids),
        )
    )

    # 清理消息
    result = db.execute(
        delete(Message).where(Message.id.in_(msg_ids))
    )

    commit_or_rollback(db)
    return result.rowcount or 0


def _cleanup_activities(db: Session, cutoff: datetime) -> int:
    """按时间清理活动记录（同时清理关联的画像来源）。"""
    activity_ids = db.scalars(
        select(Activity.id).where(Activity.created_at < cutoff)
    ).all()

    if not activity_ids:
        return 0

    # 清理活动记录
    result = db.execute(
        delete(Activity).where(Activity.id.in_(activity_ids))
    )

    commit_or_rollback(db)
    return result.rowcount or 0


def _cleanup_memories(db: Session, cutoff: datetime) -> int:
    """按时间清理记忆（同时清理关联的画像来源引用）。"""
    memory_ids = db.scalars(
        select(Memory.id).where(Memory.created_at < cutoff)
    ).all()

    if not memory_ids:
        return 0

    # 清理画像来源中指向已删除记忆的引用（memory_id 是软引用）
    db.execute(
        delete(ProfileSource).where(
            ProfileSource.source_type == "memory",
            ProfileSource.memory_id.in_(memory_ids),
        )
    )

    # 清理记忆（级联删除 MemorySource、MemoryRevision、MemoryReference）
    result = db.execute(
        delete(Memory).where(Memory.id.in_(memory_ids))
    )

    commit_or_rollback(db)
    return result.rowcount or 0


def _cleanup_backups_by_time(db: Session, cutoff: datetime) -> int:
    """按时间清理备份记录和文件。"""
    records = db.scalars(
        select(BackupRecord).where(BackupRecord.created_at < cutoff)
    ).all()

    count = 0
    for record in records:
        try:
            if os.path.exists(record.file_path):
                os.remove(record.file_path)
        except OSError as exc:
            logger.warning(f"保留策略清理备份文件失败: {record.file_path}, {exc}")

        db.delete(record)
        count += 1

    if count > 0:
        commit_or_rollback(db)

    return count


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

    for table in [ProfileRevision, ProfileSource]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    for table in [Message]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    for table in [Task]:
        count = db.execute(table.__table__.delete()).rowcount or 0
        if count > 0:
            cleared_tables.append(table.__tablename__)

    # 2. 清除主表
    main_tables = [
        Memory, Profile, ChatSession, Goal, Activity, BackgroundTask,
        AuditLog, ModelConfig, PrivacyRule, DataExport, BackupRecord,
        RetentionPolicy,
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
        "goals": lambda: db.scalar(select(func.count(Goal.id))) or 0,
        "tasks": lambda: db.scalar(select(func.count(Task.id))) or 0,
        "profiles": lambda: db.scalar(select(func.count(Profile.id))) or 0,
        "profile_sources": lambda: db.scalar(select(func.count(ProfileSource.id))) or 0,
        "profile_revisions": lambda: db.scalar(select(func.count(ProfileRevision.id))) or 0,
        "audit_logs": lambda: db.scalar(select(func.count(AuditLog.id))) or 0,
        "background_tasks": lambda: db.scalar(select(func.count(BackgroundTask.id))) or 0,
        "model_configs": lambda: db.scalar(select(func.count(ModelConfig.id))) or 0,
        "data_exports": lambda: db.scalar(select(func.count(DataExport.id))) or 0,
        "backup_records": lambda: db.scalar(select(func.count(BackupRecord.id))) or 0,
        "retention_policies": lambda: db.scalar(select(func.count(RetentionPolicy.id))) or 0,
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


def _get_policy_or_error(db: Session, policy_id: int) -> RetentionPolicy:
    """获取保留策略，不存在时抛出异常。"""
    policy = db.get(RetentionPolicy, policy_id)
    if policy is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"保留策略不存在: {policy_id}")
    return policy
