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
_CURRENT_VERSION: int = 4


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
        _set_db_version(db, _CURRENT_VERSION)
        logger.info(f"数据库初始化完成，版本 v{_CURRENT_VERSION}")
        return True

    current_version = _get_db_version(db)
    logger.info(f"当前数据库版本: v{current_version}，期望版本: v{_CURRENT_VERSION}")

    if current_version == _CURRENT_VERSION:
        # 版本匹配但仍需执行 create_all 以发现新增模型表
        # create_all 是幂等操作，不会重建已存在的表
        base_metadata.create_all(bind=db.get_bind())
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
    _set_db_version(db, _CURRENT_VERSION)
    logger.info(f"数据库重建完成，版本 v{_CURRENT_VERSION}")
    return True
