"""活动与隐私规则数据模型。

活动记录用户在桌面应用中的前台活动信息。
隐私规则定义活动采集的隐私控制策略。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, func

from app.core.base_model import BaseModel
from app.core.database import Base


class Activity(Base):
    """活动记录表。

    记录用户在桌面应用中的前台活动信息，在隐私规则允许范围内采集。
    """

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    app_name = Column(String(256), nullable=False, index=True, comment="应用名称")
    window_title = Column(String(512), nullable=True, comment="窗口标题")
    started_at = Column(DateTime, nullable=False, comment="活动开始时间")
    ended_at = Column(DateTime, nullable=True, comment="活动结束时间")
    duration_seconds = Column(
        Integer, nullable=True, comment="活动持续时长（秒）",
    )
    is_idle = Column(
        Boolean, nullable=False, default=False, comment="用户是否空闲",
    )
    platform = Column(
        String(16), nullable=False, comment="采集来源平台: macos/windows",
    )
    privacy_action = Column(
        String(32),
        nullable=False,
        default="allowed",
        comment="隐私处理结果: allowed/blocked/masked",
    )
    masked_app_name = Column(
        String(256), nullable=True, comment="脱敏后的应用名称",
    )
    masked_window_title = Column(
        String(512), nullable=True, comment="脱敏后的窗口标题",
    )
    source_id = Column(
        String(64), nullable=True, unique=True, comment="来源去重标识",
    )
    created_at = Column(
        DateTime, server_default=func.now(), nullable=False, comment="创建时间",
    )

    def __repr__(self):
        return (
            f"<Activity(id={self.id}, app='{self.app_name}', "
            f"started_at='{self.started_at}')>"
        )


# 行为统计查询的覆盖索引
Index("ix_activities_created_at_app_name", Activity.created_at, Activity.app_name)
Index("ix_activities_platform_started", Activity.platform, Activity.started_at)


class PrivacyRule(BaseModel):
    """隐私规则表。

    定义桌面活动采集的隐私控制规则。规则按优先级顺序评估。
    """

    __tablename__ = "privacy_rules"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键 ID")
    rule_type = Column(
        String(32),
        nullable=False,
        index=True,
        comment="规则类型: global_pause/app_blacklist/app_whitelist/"
        "title_keyword/time_based/content_masking/temp_pause",
    )
    rule_value = Column(
        Text, nullable=False, comment="规则值（JSON 字符串或其他格式）",
    )
    description = Column(String(256), nullable=True, comment="规则描述")
    is_active = Column(
        Boolean, nullable=False, default=True, comment="是否启用",
    )
    priority = Column(
        Integer, nullable=False, default=0, comment="优先级（数值越高优先）",
    )

    def __repr__(self):
        return (
            f"<PrivacyRule(id={self.id}, type='{self.rule_type}', "
            f"active={self.is_active})>"
        )
