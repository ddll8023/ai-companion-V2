"""应用配置。"""

from __future__ import annotations

import json

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

    # 日志级别
    LOG_LEVEL: str = "INFO"

    # CORS 配置（JSON 数组字符串）
    CORS_ORIGINS: str = '["http://127.0.0.1:9753","http://localhost:9753"]'

    @property
    def cors_origins(self) -> list[str]:
        return json.loads(self.CORS_ORIGINS)


settings = Settings()
