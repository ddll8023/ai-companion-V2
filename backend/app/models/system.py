"""系统配置数据模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Index, Integer, String, Text

from app.core.base_model import BaseModel


class ModelConfig(BaseModel):
    """模型配置表（非敏感配置）。"""

    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    name = Column(String(64), nullable=False, unique=True, comment="配置名称")
    provider = Column(String(32), nullable=False, comment="模型供应商: openai/anthropic/openai-compatible")
    model_name = Column(String(128), nullable=False, comment="模型名称")
    api_base = Column(String(256), nullable=True, comment="API 地址（可选）")
    enable_reasoning = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否展示并保存模型返回的推理过程",
    )
    is_active = Column(Boolean, nullable=False, default=False, comment="是否为激活配置")
    has_key = Column(Boolean, nullable=False, default=False, comment="是否已配置密钥")
    status = Column(String(16), nullable=False, default="inactive", comment="状态: inactive/active/error")
    error_message = Column(String(256), nullable=True, comment="错误信息（可选）")

    __table_args__ = (
        Index("ix_model_configs_is_active", "is_active"),
    )

    def __repr__(self):
        return f"<ModelConfig(id={self.id}, name='{self.name}', provider='{self.provider}')>"
