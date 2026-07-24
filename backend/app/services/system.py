"""系统状态聚合服务。

聚合本地服务、数据库、模型配置、检索、权限、后台任务等各项能力的运行状态。
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


def get_database_status(db: Session) -> dict[str, Any]:
    """获取数据库状态。"""
    try:
        # 检查数据库连接
        db.execute(text("SELECT 1"))

        # 获取数据库文件大小
        db_file = settings.db_file_path
        file_size_bytes = 0
        if os.path.exists(db_file):
            file_size_bytes = os.path.getsize(db_file)

        # 检查 FTS5 表
        # 注意：使用 content 表（普通表）查询，避免 FTS5 影子表 COUNT 性能问题
        fts5_ready = False
        fts5_count = 0
        try:
            fts5_count = db.execute(
                text("SELECT COUNT(*) FROM memories_fts_content")
            ).scalar() or 0
            fts5_ready = True
        except Exception:
            fts5_ready = False

        # 获取各表记录数
        from app.models.activity import Activity
        from app.models.audit import AuditLog
        from app.models.chat import Message, Session as ChatSession
        from app.models.data_governance import BackupRecord, DataExport
        from app.models.goal import Goal, Task
        from app.models.memory import Memory
        from app.models.profile import Profile
        from app.models.task import BackgroundTask

        return {
            "status": "ok",
            "ready": True,
            "file_size_bytes": file_size_bytes,
            "fts5_ready": fts5_ready,
            "fts5_index_count": fts5_count,
            # 注意：不返回 path 字段，Renderer 不得获得数据库路径
            "table_counts": {
                "sessions": db.query(ChatSession).count(),
                "messages": db.query(Message).count(),
                "memories": db.query(Memory).count(),
                "activities": db.query(Activity).count(),
                "goals": db.query(Goal).count(),
                "tasks": db.query(Task).count(),
                "profiles": db.query(Profile).count(),
                "audit_logs": db.query(AuditLog).count(),
                "background_tasks": db.query(BackgroundTask).count(),
                "data_exports": db.query(DataExport).count(),
                "backup_records": db.query(BackupRecord).count(),
            },
        }
    except Exception as exc:
        logger.error(f"数据库状态检查失败: {exc}")
        return {
            "status": "error",
            "error_message": str(exc)[:200],
            "ready": False,
            "file_size_bytes": 0,
            "fts5_ready": False,
            "fts5_index_count": 0,
            "table_counts": {},
        }


def get_model_config_status(db: Session) -> dict[str, Any]:
    """获取模型配置状态。"""
    try:
        from app.models.system import ModelConfig

        total = db.query(ModelConfig).count()
        active = db.query(ModelConfig).filter(
            ModelConfig.is_active == 1
        ).count()
        has_error = db.query(ModelConfig).filter(
            ModelConfig.status == "error"
        ).count()

        active_config = None
        if active > 0:
            config = db.query(ModelConfig).filter(
                ModelConfig.is_active == 1
            ).first()
            if config:
                active_config = {
                    "id": config.id,
                    "name": config.name,
                    "provider": config.provider,
                    "model_name": config.model_name,
                    "status": config.status,
                    "has_key": bool(config.has_key),
                    "error_message": config.error_message,
                }

        return {
            "status": "ok",
            "total_configs": total,
            "active_count": active,
            "error_count": has_error,
            "active_config": active_config,
            "configured": total > 0,
            "available": active > 0,
        }
    except Exception as exc:
        logger.error(f"模型配置状态检查失败: {exc}")
        return {
            "status": "error",
            "error_message": str(exc)[:200],
            "total_configs": 0,
            "active_count": 0,
            "error_count": 0,
            "active_config": None,
            "configured": False,
            "available": False,
        }


def get_task_backlog(db: Session) -> dict[str, Any]:
    """获取后台任务积压统计。"""
    try:
        from app.models.task import BackgroundTask

        pending = db.query(BackgroundTask).filter(
            BackgroundTask.status == "pending"
        ).count()
        running = db.query(BackgroundTask).filter(
            BackgroundTask.status == "running"
        ).count()
        failed = db.query(BackgroundTask).filter(
            BackgroundTask.status == "failed"
        ).count()
        retrying = db.query(BackgroundTask).filter(
            BackgroundTask.status == "retrying"
        ).count()

        return {
            "status": "ok",
            "pending": pending,
            "running": running,
            "failed": failed,
            "retrying": retrying,
            "total_backlog": pending + running + retrying,
            "healthy": pending < 50,
        }
    except Exception as exc:
        logger.error(f"后台任务积压统计失败: {exc}")
        return {
            "status": "error",
            "error_message": str(exc)[:200],
            "pending": 0,
            "running": 0,
            "failed": 0,
            "retrying": 0,
            "total_backlog": 0,
            "healthy": True,
        }


def get_backup_status(db: Session) -> dict[str, Any]:
    """获取备份状态。"""
    try:
        from app.models.data_governance import BackupRecord

        total = db.query(BackupRecord).count()
        latest = db.query(BackupRecord).order_by(
            BackupRecord.created_at.desc()
        ).first()

        return {
            "status": "ok",
            "total_backups": total,
            "latest_backup_at": (
                latest.created_at.isoformat() if latest else None
            ),
            "latest_backup_status": latest.status if latest else None,
            "latest_backup_size_bytes": (
                latest.file_size_bytes if latest else None
            ),
        }
    except Exception as exc:
        logger.error(f"备份状态检查失败: {exc}")
        return {
            "status": "error",
            "error_message": str(exc)[:200],
            "total_backups": 0,
            "latest_backup_at": None,
            "latest_backup_status": None,
            "latest_backup_size_bytes": None,
        }


def get_activity_collection_status(db: Session) -> dict[str, Any]:
    """获取活动采集状态。"""
    try:
        from app.models.activity import Activity, PrivacyRule

        total_rules = db.query(PrivacyRule).count()
        active_rules = db.query(PrivacyRule).filter(
            PrivacyRule.is_active == True  # noqa: E712
        ).count()
        # 使用 Python UTC 时间，避免 func.now() 时区偏移风险
        today_str = datetime.now(timezone.utc).date().isoformat()
        today_count = db.query(Activity).filter(
            func.date(Activity.created_at) == today_str
        ).count()
        total_activities = db.query(Activity).count()

        return {
            "status": "ok",
            "privacy_rules_total": total_rules,
            "privacy_rules_active": active_rules,
            "activities_today": today_count,
            "activities_total": total_activities,
        }
    except Exception as exc:
        logger.error(f"活动采集状态检查失败: {exc}")
        return {
            "status": "error",
            "error_message": str(exc)[:200],
            "privacy_rules_total": 0,
            "privacy_rules_active": 0,
            "activities_today": 0,
            "activities_total": 0,
        }


def get_data_directory_status() -> dict[str, Any]:
    """获取数据目录状态。"""
    data_dir = settings.resolved_data_dir
    writable = False
    file_count = 0
    total_size = 0
    limited = False

    try:
        os.makedirs(data_dir, exist_ok=True)
        writable = os.access(data_dir, os.W_OK)

        # 限制：最多扫描 10000 个文件，避免大量文件时阻塞 HTTP 响应
        MAX_SCAN_FILES = 10000
        for root, _dirs, files in os.walk(data_dir):
            for fname in files:
                if file_count >= MAX_SCAN_FILES:
                    limited = True
                    break
                fpath = os.path.join(root, fname)
                try:
                    file_count += 1
                    total_size += os.path.getsize(fpath)
                except Exception:
                    pass
            if file_count >= MAX_SCAN_FILES:
                break
    except Exception:
        writable = False

    return {
        "path": data_dir,
        "writable": writable,
        "file_count": file_count,
        "total_size_bytes": total_size,
        "scan_limited": limited,
    }


def get_system_status(
    db: Session,
    db_ready: bool,
    db_migration_completed: bool,
) -> dict[str, Any]:
    """聚合全部系统状态。"""
    database = get_database_status(db)
    model_config = get_model_config_status(db)
    task_backlog = get_task_backlog(db)
    backup = get_backup_status(db)
    activity = get_activity_collection_status(db)
    data_dir = get_data_directory_status()

    return {
        "service": {
            "name": "AI Companion",
            "version": settings.APP_VERSION,
            "status": "running",
            "uptime": None,  # 后续可由进程管理跟踪
        },
        "database": {
            **database,
            "migration_completed": db_migration_completed,
        },
        "model_config": model_config,
        "data_directory": data_dir,
        "background_tasks": task_backlog,
        "backup": backup,
        "activity_collection": activity,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
