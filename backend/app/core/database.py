"""数据库引擎、会话管理和模型基类。"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from contextlib import contextmanager

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
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


def paginate_query(
    db: Session,
    stmt: select,
    page: int,
    page_size: int,
    response_class: type | None = None,
    transform: Callable | None = None,
    ordering: select | None = None,
) -> PaginatedResponse:
    """通用分页查询。

    消除各 service 层重复的分页+count+model_validate 模板代码。

    Args:
        db: 数据库会话
        stmt: 已构造好的 SQLAlchemy select 语句（不含 offset/limit）
        page: 页码，从 1 开始
        page_size: 每页条数
        response_class: Pydantic 响应类，用于 model_validate 转换
        transform: 自定义转换函数（与 response_class 二选一）
        ordering: 排序子句（如 Model.created_at.desc()），会追加到 stmt

    Returns:
        分页后的 PaginatedResponse 实例
    """
    # 应用排序
    if ordering is not None:
        stmt = stmt.order_by(ordering)

    # 统计数据总量
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # 分页查询
    items = db.scalars(
        stmt.offset((page - 1) * page_size).limit(page_size)
    ).all()

    # 转换结果
    if transform is not None:
        lists = [transform(item) for item in items]
    elif response_class is not None:
        lists = [response_class.model_validate(item) for item in items]
    else:
        lists = list(items)

    return PaginatedResponse(
        lists=lists,
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        ),
    )
