"""数据库引擎、会话管理和模型基类。"""

from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.schemas.common import ErrorCode
from app.utils.exception import ServiceException

# 确保数据目录存在
_db_dir = os.path.dirname(settings.db_file_path)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """设置 SQLite 连接时的 pragma 参数。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """ORM 模型基类。"""

    pass


def get_db():
    """FastAPI 依赖注入：获取数据库会话。"""
    with SessionLocal() as db:
        try:
            yield db
        except Exception as exc:
            db.rollback()
            raise ServiceException(ErrorCode.INTERNAL_ERROR, str(exc)) from exc


@contextmanager
def get_background_db_session():
    """获取后台任务数据库会话（上下文管理器，自动关闭）。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def commit_or_rollback(db: Session):
    """提交当前事务，失败时回滚并转换为业务异常。"""
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise ServiceException(ErrorCode.INTERNAL_ERROR, str(exc)) from exc
