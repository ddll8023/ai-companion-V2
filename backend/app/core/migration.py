"""数据库迁移管理。

新数据库从空状态初始化，已有数据库检查版本号。
版本匹配时也执行 create_all 以发现新增模型表（幂等操作）。
版本不匹配时重建表结构（开发阶段简化策略）。
"""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 用于存储数据库版本的表名
_VERSION_TABLE = "_db_version"
# 当前代码期望的数据库版本
#
# 版本变更记录:
#   v1 — 初始创建: sessions, messages, model_configs, audit_logs
#   v2 — 添加: background_tasks
#   v3 — 未记录变更
#   v4 — 未记录变更
#   v5 — 添加: memories, memory_sources, memory_revisions
#   v6 — 添加: memory_references, memories_fts (FTS5 虚拟表)
#   v7 — 添加: data_exports, backup_records, retention_policies（数据治理模块）
#   v8 — 添加: memories.embedding（向量嵌入 BLOB 列）
#
# 注意: 开发阶段版本不匹配时会清空数据重建，生产阶段需实现逐版本迁移。
_CURRENT_VERSION: int = 8


def _ensure_version_table(db: Session):
    """创建版本表（如不存在）。"""
    db.execute(
        text(
            f"""
        CREATE TABLE IF NOT EXISTS {_VERSION_TABLE} (
            version INTEGER NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
        )
    )
    db.commit()


def _get_db_version(db: Session) -> int | None:
    """获取当前数据库版本号。"""
    result = db.execute(
        text(f"SELECT version FROM {_VERSION_TABLE} ORDER BY rowid DESC LIMIT 1")
    ).scalar()
    return result


def _set_db_version(db: Session, version: int):
    """设置数据库版本号。"""
    db.execute(text(f"INSERT INTO {_VERSION_TABLE} (version) VALUES (:v)"), {"v": version})
    db.commit()


def _ensure_fts5_table(db: Session, rebuild: bool = False):
    """创建或同步 FTS5 虚拟表。

    FTS5 用于记忆全文检索，不通过 SQLAlchemy ORM 管理。

    Args:
        db: 数据库会话
        rebuild: 是否全量重建索引（仅新数据库创建或索引损坏时 True）
    """
    try:
        # 创建 FTS5 表（幂等操作，表已存在则跳过）
        db.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts "
            "USING fts5(content, memory_id UNINDEXED, type UNINDEXED)"
        ))
        db.commit()

        if rebuild:
            # 全量重建：清除后从已确认的记忆中重新插入
            db.execute(text("DELETE FROM memories_fts"))
            db.commit()
            db.execute(text(
                "INSERT INTO memories_fts (content, memory_id, type) "
                "SELECT content, id, type FROM memories "
                "WHERE status IN ('confirmed', 'corrected')"
            ))
            db.commit()
            logger.info("FTS5 索引已全量重建")

            # 全量重建嵌入向量（不阻塞主流程）
            _rebuild_embeddings(db)
        else:
            logger.debug("FTS5 表已就绪（增量维护）")
    except Exception as exc:
        logger.warning(f"FTS5 表创建失败（检索功能降级）: {exc}")


def _rebuild_embeddings(db: Session):
    """全量重建记忆嵌入向量。

    扫描所有 confirmed/corrected 状态的记忆，批量生成嵌入向量。
    向量不可用时不阻塞（静默降级）。
    """
    try:
        from sqlalchemy import select
        from app.models.memory import Memory
        from app.services.embedding import embed_texts, serialize_embedding, _ensure_model

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
        logger.warning("嵌入向量重建失败（可降级，不影响基础检索）: %s", exc)
        db.rollback()


def ensure_schema(db: Session, base_metadata, db_file_path: str):
    """确保数据库 schema 与当前模型定义一致。

    新数据库 → 创建所有表
    已有数据库版本匹配 → 同步新增表（create_all 幂等）
    版本不匹配 → 重建表（开发阶段）

    Args:
        db: 数据库会话
        base_metadata: SQLAlchemy Base.metadata
        db_file_path: 数据库文件路径，用于判断是否为新数据库

    Returns:
        bool: True 表示 schema 已就绪
    """
    is_new = not os.path.exists(db_file_path) or os.path.getsize(db_file_path) == 0

    _ensure_version_table(db)

    if is_new:
        logger.info("新数据库，创建所有表")
        base_metadata.create_all(bind=db.get_bind())
        _ensure_fts5_table(db, rebuild=True)
        _set_db_version(db, _CURRENT_VERSION)
        logger.info(f"数据库初始化完成，版本 v{_CURRENT_VERSION}")
        return True

    current_version = _get_db_version(db)
    if current_version is None:
        # 版本表存在但无记录 → 视为新数据库
        logger.info("版本表为空，按新数据库处理")
        _set_db_version(db, _CURRENT_VERSION)
        _ensure_fts5_table(db, rebuild=True)
        return True
    logger.info(f"当前数据库版本: v{current_version}，期望版本: v{_CURRENT_VERSION}")

    if current_version == _CURRENT_VERSION:
        # 版本匹配但仍需执行 create_all 以发现新增模型表
        # create_all 是幂等操作，不会重建已存在的表
        base_metadata.create_all(bind=db.get_bind())
        _ensure_fts5_table(db, rebuild=False)
        logger.info("数据库版本匹配，已同步新增表（如有）")
        return True

    # 开发阶段：版本不匹配时重建
    logger.warning(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    logger.warning(
        f"数据库版本 v{current_version} 与期望 v{_CURRENT_VERSION} 不匹配"
    )
    logger.warning("即将清空全部已有数据并重建表结构！")
    logger.warning(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    base_metadata.drop_all(bind=db.get_bind())
    base_metadata.create_all(bind=db.get_bind())
    _ensure_fts5_table(db, rebuild=True)
    _set_db_version(db, _CURRENT_VERSION)
    logger.info(f"数据库重建完成，版本 v{_CURRENT_VERSION}")
    return True
