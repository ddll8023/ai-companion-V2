"""数据库迁移管理。

新数据库从空状态初始化，已有数据库检查版本号并逐版本增量迁移。
版本匹配时也执行 create_all 以发现新增模型表（幂等操作）。
不再采用版本不匹配时删表重建的简化策略。
"""

from __future__ import annotations

import os
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

_VERSION_TABLE = "_db_version"

# 版本变更记录:
#   v1 — 初始创建: sessions, messages, model_configs, audit_logs
#   v2 — 添加: background_tasks
#   v3 — 添加: goals, tasks (目标与任务模块)
#   v4 — 添加: memories, memory_sources, memory_revisions
#   v5 — 添加: memory_references, memories_fts (FTS5 虚拟表)
#   v6 — 添加: data_exports, backup_records, retention_policies (数据治理模块)
#   v7 — 添加: memories.embedding (向量嵌入 BLOB 列)
#   v8 — 添加: audit_logs 字段 (actor_id, actor_name, ip_address)
#   v9 — 添加: messages.reasoning_content（模型推理过程）
#   v10 — 添加: model_configs.enable_reasoning（推理展示开关）
#   v11 — 添加: memory_sources.evidence_text（用户原文证据）
#   v13 — 会话级提取字段调整（新数据库直接重建）
#   v14 — 新增 observations/insights/insight_evidence/insight_relations/
#         insight_revisions/persona_states/persona_documents 人物理解体系
_CURRENT_VERSION: int = 14


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


# ========================================================================
# 逐版本迁移函数
# ========================================================================


def _migrate_v1_to_v2(db: Session) -> None:
    """v1 → v2: 新增 background_tasks 表。"""
    from app.models.task import BackgroundTask  # noqa: F401

    from app.core.database import Base

    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v1→v2: 创建 background_tasks 表")


def _migrate_v2_to_v3(db: Session) -> None:
    """v2 → v3: 新增 goals 和 tasks 表。"""
    from app.models.goal import Goal, Task  # noqa: F401

    from app.core.database import Base

    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v2→v3: 创建 goals, tasks 表")


def _migrate_v3_to_v4(db: Session) -> None:
    """v3 → v4: 新增 memories 系列表。"""
    from app.models.memory import Memory, MemorySource, MemoryRevision  # noqa: F401

    from app.core.database import Base

    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v3→v4: 创建 memories, memory_sources, memory_revisions 表")


def _migrate_v4_to_v5(db: Session) -> None:
    """v4 → v5: 新增 memory_references 表和 FTS5 虚拟表。"""
    from app.models.memory import MemoryReference  # noqa: F401

    from app.core.database import Base

    Base.metadata.create_all(bind=db.get_bind())

    # 创建 FTS5 虚拟表
    db.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts "
        "USING fts5(content, memory_id UNINDEXED, type UNINDEXED)"
    ))
    db.commit()

    # 全量重建 FTS5 索引
    db.execute(text("DELETE FROM memories_fts"))
    db.commit()
    db.execute(text(
        "INSERT INTO memories_fts (content, memory_id, type) "
        "SELECT content, id, type FROM memories "
        "WHERE status IN ('confirmed', 'corrected')"
    ))
    db.commit()
    logger.info("迁移 v4→v5: 创建 memory_references 表和 FTS5 索引")


def _migrate_v5_to_v6(db: Session) -> None:
    """v5 → v6: 新增数据治理模块表。"""
    from app.models.data_governance import DataExport, BackupRecord, RetentionPolicy  # noqa: F401

    from app.core.database import Base

    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v5→v6: 创建 data_exports, backup_records, retention_policies 表")


def _migrate_v6_to_v7(db: Session) -> None:
    """v6 → v7: memories 表增加 embedding BLOB 列。"""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    columns = [col["name"] for col in inspector.get_columns("memories")]
    if "embedding" not in columns:
        db.execute(text("ALTER TABLE memories ADD COLUMN embedding BLOB"))
        db.commit()
        logger.info("迁移 v6→v7: memories 表增加 embedding 列")
    else:
        logger.info("迁移 v6→v7: embedding 列已存在，跳过")


def _migrate_v7_to_v8(db: Session) -> None:
    """v7 → v8: audit_logs 表增加 actor 相关字段。"""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    columns = [col["name"] for col in inspector.get_columns("audit_logs")]
    for col_name, col_type in [
        ("actor_id", "INTEGER"),
        ("actor_name", "VARCHAR(64)"),
        ("ip_address", "VARCHAR(45)"),
    ]:
        if col_name not in columns:
            db.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {col_name} {col_type}"))
            db.commit()
            logger.info("迁移 v7→v8: audit_logs 表增加 %s 列", col_name)


def _migrate_v8_to_v9(db: Session) -> None:
    """v8 → v9: messages 表增加可选的推理过程字段。"""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    columns = [col["name"] for col in inspector.get_columns("messages")]
    if "reasoning_content" not in columns:
        db.execute(text("ALTER TABLE messages ADD COLUMN reasoning_content TEXT"))
        db.commit()
        logger.info("迁移 v8→v9: messages 表增加 reasoning_content 列")
    else:
        logger.info("迁移 v8→v9: reasoning_content 列已存在，跳过")


def _migrate_v9_to_v10(db: Session) -> None:
    """v9 → v10: 模型配置增加推理展示开关。"""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    columns = [col["name"] for col in inspector.get_columns("model_configs")]
    if "enable_reasoning" not in columns:
        db.execute(text(
            "ALTER TABLE model_configs "
            "ADD COLUMN enable_reasoning BOOLEAN NOT NULL DEFAULT 0"
        ))
        db.commit()
        logger.info("迁移 v9→v10: model_configs 表增加 enable_reasoning 列")
    else:
        logger.info("迁移 v9→v10: enable_reasoning 列已存在，跳过")


def _migrate_v10_to_v11(db: Session) -> None:
    """v10 → v11: 记忆来源增加用户原文证据字段。"""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    columns = [col["name"] for col in inspector.get_columns("memory_sources")]
    if "evidence_text" not in columns:
        db.execute(text(
            "ALTER TABLE memory_sources ADD COLUMN evidence_text VARCHAR(512)"
        ))
        db.commit()
        logger.info("迁移 v10→v11: memory_sources 表增加 evidence_text 列")
    else:
        logger.info("迁移 v10→v11: evidence_text 列已存在，跳过")


def _migrate_v11_to_v12(db: Session) -> None:
    """v11 → v12: 创建对话轮次、会话摘要和 AI 内容项表。"""
    from app.models.conversation import AiArtifact, ConversationTurn, SessionSummary  # noqa: F401
    from app.core.database import Base
    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v11→v12: 创建内容治理相关表")


def _migrate_v12_to_v13(db: Session) -> None:
    """v12 → v13: 会话提取结构调整。"""
    from app.core.database import Base
    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v12→v13: 同步会话提取结构")


def _migrate_v13_to_v14(db: Session) -> None:
    """v13 → v14: 创建人物理解体系表。"""
    from app.models.persona import Insight, InsightEvidence, InsightRelation, InsightRevision, Observation, PersonaDocument, PersonaState  # noqa: F401
    from app.core.database import Base
    Base.metadata.create_all(bind=db.get_bind())
    logger.info("迁移 v13→v14: 创建人物理解相关表")


# 迁移注册表：key=目标版本号，value=迁移函数
_VERSION_MIGRATIONS: dict[int, Callable[[Session], None]] = {
    2: _migrate_v1_to_v2,
    3: _migrate_v2_to_v3,
    4: _migrate_v3_to_v4,
    5: _migrate_v4_to_v5,
    6: _migrate_v5_to_v6,
    7: _migrate_v6_to_v7,
    8: _migrate_v7_to_v8,
    9: _migrate_v8_to_v9,
    10: _migrate_v9_to_v10,
    11: _migrate_v10_to_v11,
    12: _migrate_v11_to_v12,
    13: _migrate_v12_to_v13,
    14: _migrate_v13_to_v14,
}


def _apply_migrations(db: Session, current_version: int) -> None:
    """逐版本应用迁移。

    Args:
        db: 数据库会话
        current_version: 当前数据库的实际版本

    Raises:
        RuntimeError: 某版本迁移函数未定义时终止
    """
    for target_version in range(current_version + 1, _CURRENT_VERSION + 1):
        migration_fn = _VERSION_MIGRATIONS.get(target_version)
        if migration_fn is None:
            raise RuntimeError(
                f"版本 v{target_version} 的迁移函数未定义。"
                f"当前版本 v{current_version}，目标版本 v{_CURRENT_VERSION}。"
                f"无法自动升级。"
            )
        logger.info("━━ 执行迁移: v%d → v%d ━━", target_version - 1, target_version)
        migration_fn(db)
        _set_db_version(db, target_version)
        logger.info("迁移完成: v%d → v%d", target_version - 1, target_version)


# ========================================================================
# FTS5 与嵌入向量重建
# ========================================================================


def _ensure_fts5_table(db: Session, rebuild: bool = False):
    """创建或同步 FTS5 虚拟表。

    FTS5 用于记忆全文检索，不通过 SQLAlchemy ORM 管理。

    Args:
        db: 数据库会话
        rebuild: 是否全量重建索引（仅新数据库创建或索引损坏时 True）
    """
    try:
        db.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts "
            "USING fts5(content, memory_id UNINDEXED, type UNINDEXED)"
        ))
        db.commit()

        if rebuild:
            db.execute(text("DELETE FROM memories_fts"))
            db.commit()
            db.execute(text(
                "INSERT INTO memories_fts (content, memory_id, type) "
                "SELECT content, id, type FROM memories "
                "WHERE status IN ('confirmed', 'corrected')"
            ))
            db.commit()
            logger.info("FTS5 索引已全量重建")

            _rebuild_embeddings(db)
        else:
            logger.debug("FTS5 表已就绪（增量维护）")
    except Exception as exc:
        logger.warning(f"FTS5 表创建失败（检索功能降级）: {exc}")


def _rebuild_embeddings(db: Session):
    """全量重建记忆嵌入向量。"""
    try:
        from sqlalchemy import select

        from app.models.memory import Memory
        from app.services.embedding import _ensure_model, embed_texts, serialize_embedding

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


# ========================================================================
# 入口函数
# ========================================================================


def ensure_schema(db: Session, base_metadata, db_file_path: str):
    """确保数据库 schema 与当前模型定义一致。

    新数据库 → 创建所有表
    已有数据库版本匹配 → 同步新增表（create_all 幂等）
    版本不匹配 → 逐版本增量迁移（不再删表重建）

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
        logger.info("版本表为空，按新数据库处理")
        _set_db_version(db, _CURRENT_VERSION)
        _ensure_fts5_table(db, rebuild=True)
        return True

    logger.info(f"当前数据库版本: v{current_version}，期望版本: v{_CURRENT_VERSION}")

    if current_version == _CURRENT_VERSION:
        base_metadata.create_all(bind=db.get_bind())
        _ensure_fts5_table(db, rebuild=False)
        logger.info("数据库版本匹配，已同步新增表（如有）")
        return True

    # 版本不匹配 → 逐版本增量迁移
    if current_version < _CURRENT_VERSION:
        logger.warning("数据库版本 v%d → v%d，执行增量迁移", current_version, _CURRENT_VERSION)
        try:
            _apply_migrations(db, current_version)
        except RuntimeError as exc:
            logger.error(str(exc))
            logger.error(
                "迁移失败。如需回退，请手动删除数据库文件后重启。"
            )
            return False
        # 迁移完成后执行 create_all 确保同步新增的 ORM 注册表
        base_metadata.create_all(bind=db.get_bind())
        _ensure_fts5_table(db, rebuild=False)
        logger.info("数据库从 v%d 升级到 v%d 完成", current_version, _CURRENT_VERSION)
        return True

    # 当前版本比代码版本新（降级）
    logger.warning(
        "数据库版本 v%d 比代码期望的 v%d 新。"
        "可能降级了项目版本。保留现有表结构并尝试同步。",
        current_version, _CURRENT_VERSION,
    )
    base_metadata.create_all(bind=db.get_bind())
    _ensure_fts5_table(db, rebuild=False)
    return True
