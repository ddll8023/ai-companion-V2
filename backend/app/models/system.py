"""系统配置数据模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class ModelConfig(Base):
    """模型配置表（非敏感配置）。"""

    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    name = Column(String(64), nullable=False, comment="配置名称")
    provider = Column(String(32), nullable=False, comment="模型供应商: openai/anthropic/openai-compatible")
    model_name = Column(String(128), nullable=False, comment="模型名称")
    api_base = Column(String(256), nullable=True, comment="API 地址（可选）")
    is_active = Column(Integer, nullable=False, default=0, comment="是否为激活配置: 0=否, 1=是")
    has_key = Column(Integer, nullable=False, default=0, comment="是否已配置密钥: 0=否, 1=是")
    status = Column(String(16), nullable=False, default="inactive", comment="状态: inactive/active/error")
    error_message = Column(String(256), nullable=True, comment="错误信息（可选）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间",
    )

    def __repr__(self):
        return f"<ModelConfig(id={self.id}, name='{self.name}', provider='{self.provider}')>"
