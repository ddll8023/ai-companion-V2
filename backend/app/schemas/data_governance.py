"""数据治理 Pydantic Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── 导出 ─────────────────────────────────────────────────────────────────────


class DataExportRequest(BaseModel):
    """数据导出请求。"""

    export_type: str = Field(default="full", description="导出类型: full/partial")
    scope: list[str] | None = Field(
        default=None,
        description="导出范围（模块列表，如 ['sessions', 'memories', 'activities']）；full 类型忽略此参数",
    )
    start_time: datetime | None = Field(default=None, description="开始时间（可选）")
    end_time: datetime | None = Field(default=None, description="结束时间（可选）")


class DataExportResponse(BaseModel):
    """数据导出响应。"""

    id: int
    export_type: str = "full"
    scope: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: str = "completed"
    file_path: str
    file_size_bytes: int | None = None
    record_count: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ── 备份 ──────────────────────────────────────────────────────────────────────


class BackupResponse(BaseModel):
    """备份记录响应。"""

    id: int
    file_path: str
    file_size_bytes: int | None = None
    status: str = "completed"
    error_message: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BackupListQuery(BaseModel):
    """备份列表查询参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# ── 清除全部数据 ──────────────────────────────────────────────────────────────


class ClearDataRequest(BaseModel):
    """清除全部数据请求。"""

    confirm_key: str = Field(
        ...,
        description="确认密钥，需传入 'CLEAR ALL DATA' 以确认此操作不可逆",
    )


class ClearDataResponse(BaseModel):
    """清除全部数据响应。"""

    cleared_tables: list[str]
    cleared_backups: bool = False
    cleared_exports: bool = False


# ── 数据量统计 ────────────────────────────────────────────────────────────────


class DataVolumeStats(BaseModel):
    """数据量统计响应。"""

    sessions: int = 0
    messages: int = 0
    memories: int = 0
    memory_sources: int = 0
    memory_revisions: int = 0
    memory_references: int = 0
    activities: int = 0
    privacy_rules: int = 0
    observations: int = 0
    insights: int = 0
    insight_evidence: int = 0
    insight_revisions: int = 0
    persona_states: int = 0
    persona_documents: int = 0
    audit_logs: int = 0
    background_tasks: int = 0
    model_configs: int = 0
    data_exports: int = 0
    backup_records: int = 0


class ExportListQuery(BaseModel):
    """导出记录列表查询参数。"""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
