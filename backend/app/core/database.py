"""数据库引擎、会话管理和模型基类。"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.schemas.common import ErrorCode
from app.utils.exception import ServiceException

# 确保数据目录存在
_db_url = settings.DATABASE_URL
if _db_url.startswith("sqlite:///"):
    _db_path = _db_url[len("sqlite:///") :]
    if _db_path and _db_path != ":memory:":
        _db_dir = os.path.dirname(_db_path)
        if _db_dir:
            os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
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
            raise ServiceException(ErrorCode.INTERNAL_ERROR, "操作失败") from exc


def get_background_db_session():
    """获取后台任务数据库会话。"""
    return SessionLocal()


def commit_or_rollback(db: Session):
    """提交当前事务，失败时回滚并转换为业务异常。"""
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise ServiceException(ErrorCode.INTERNAL_ERROR, "操作失败") from exc
