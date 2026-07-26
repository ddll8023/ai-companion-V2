"""应用配置。"""

from __future__ import annotations

import json
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量和 .env 文件读取。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 服务地址
    HOST: str = "127.0.0.1"
    PORT: int = 18080

    # 数据库
    DATABASE_URL: str = "sqlite:///./data/ai_companion.db"

    # 数据目录（浏览器开发模式使用默认值，Electron 正式环境由主进程传入）
    DATA_DIR: str = ""

    # 日志级别
    LOG_LEVEL: str = "INFO"

    # 应用版本（所有地方统一引用此处，避免硬编码）
    APP_VERSION: str = "0.1.0"

    # 认证令牌（Electron 环境由主进程传入，必须设置）
    AUTH_TOKEN: str

    # CORS 配置（JSON 数组字符串）
    CORS_ORIGINS: str = '["http://127.0.0.1:9753","http://localhost:9753"]'

    @property
    def cors_origins(self) -> list[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            # 解析失败时使用安全默认值
            return ["http://127.0.0.1:9753"]

    @property
    def resolved_data_dir(self) -> str:
        """解析后的数据目录路径。"""
        if self.DATA_DIR:
            return os.path.abspath(self.DATA_DIR)
        # 浏览器开发模式：使用 backend/data/
        return os.path.abspath(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        )

    @property
    def db_file_path(self) -> str:
        """数据库文件路径（基于数据目录）。"""
        resolved_dir = self.resolved_data_dir
        if self.DATABASE_URL.startswith("sqlite:///"):
            return os.path.join(resolved_dir, "ai_companion.db")
        return self.DATABASE_URL

    @property
    def database_url(self) -> str:
        """基于数据目录的数据库连接 URL。"""
        if self.DATABASE_URL.startswith("sqlite:///"):
            db_path = self.db_file_path
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            return f"sqlite:///{db_path}"
        return self.DATABASE_URL


settings = Settings()
