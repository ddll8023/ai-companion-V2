"""ORM 模型基类 Mixin。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, func

from app.core.database import Base


class TimestampMixin:
    """创建时间/更新时间 Mixin。

    所有含 created_at / updated_at 字段的 Model 都应继承此类。
    """

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )


class BaseModel(Base, TimestampMixin):
    """含时间戳的 ORM 基类。

    所有表模型直接继承此类，比继承 Base + 手动声明时间戳更简洁。
    不含时间戳的特殊表单独处理。
    """

    __abstract__ = True
