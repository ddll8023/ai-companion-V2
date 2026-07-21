"""FastAPI 应用入口。"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, SessionLocal
from app.core.migration import ensure_schema
from app.schemas.common import ErrorCode
from app.schemas.response import error, success
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 标记数据库状态
_db_ready = False
_db_migration_completed = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    global _db_ready, _db_migration_completed

    logger.info("服务启动中...")
    logger.info(f"数据目录: {settings.resolved_data_dir}")
    logger.info(f"数据库文件: {settings.db_file_path}")

    # 初始化数据库迁移
    try:
        db = SessionLocal()
        db_ready = ensure_schema(
            db=db,
            base_metadata=Base.metadata,
            db_file_path=settings.db_file_path,
        )
        _db_ready = db_ready
        _db_migration_completed = db_ready
        db.close()
    except Exception as exc:
        _db_ready = False
        _db_migration_completed = False
        logger.error(f"数据库初始化失败: {exc}", exc_info=True)
        logger.warning("服务将以数据库不可用状态启动")

    yield

    _db_ready = False
    _db_migration_completed = False
    logger.info("服务关闭")


app = FastAPI(
    title="AI Companion",
    version="0.1.0",
    description="AI Companion 本地业务服务",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理器
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    return JSONResponse(
        status_code=200,
        content=error(code=exc.code, message=exc.message, data=exc.data),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=200,
        content=error(code=ErrorCode.INTERNAL_ERROR, message="服务器内部错误"),
    )


# 注册路由
from app.api import audit as api_audit
from app.api import models as api_models

app.include_router(api_audit.router)
app.include_router(api_models.router)


# ── 认证中间件（Electron 安全通信） ──────────────────────────────
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """验证请求认证令牌。

    健康检查路由 /health 不要求认证（用于启动检测）。
    当 AUTH_TOKEN 为空时跳过认证（浏览器开发模式）。
    """
    if request.url.path in ("/health", "/api/health", "/docs", "/openapi.json"):
        return await call_next(request)

    if settings.AUTH_TOKEN:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:] != settings.AUTH_TOKEN:
            return JSONResponse(
                status_code=401,
                content=error(code=ErrorCode.PERMISSION_DENIED, message="认证失败"),
            )

    return await call_next(request)


def _health_data() -> dict:
    """返回健康检查数据（供多个路由共享）。"""
    data_dir = settings.resolved_data_dir
    data_dir_writable = _check_dir_writable(data_dir)
    db_file = settings.db_file_path

    return {
        "status": "running",
        "service": "AI Companion",
        "version": "0.1.0",
        "database": {
            "ready": _db_ready,
            "migration_completed": _db_migration_completed,
            "path": db_file,
        },
        "data_directory": {
            "path": data_dir,
            "writable": data_dir_writable,
        },
    }


@app.get("/health")
async def health():
    """健康检查（浏览器直接访问用）。"""
    return success(data=_health_data())


@app.get("/api/health")
async def api_health():
    """健康检查（前端 /api 代理用，与业务路由前缀一致）。"""
    return success(data=_health_data())


def _check_dir_writable(dir_path: str) -> bool:
    """检查目录是否可写。"""
    try:
        os.makedirs(dir_path, exist_ok=True)
        test_file = os.path.join(dir_path, ".write_test")
        with open(test_file, "w") as f:
            f.write("")
        os.unlink(test_file)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
