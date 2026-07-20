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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    global _db_ready

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
        db.close()
    except Exception as exc:
        _db_ready = False
        logger.error(f"数据库初始化失败: {exc}", exc_info=True)
        logger.warning("服务将以数据库不可用状态启动")

    yield

    _db_ready = False
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

app.include_router(api_audit.router)


# 健康检查
@app.get("/health")
async def health():
    """增强健康检查：返回服务、数据库、数据目录和迁移状态。"""
    data_dir = settings.resolved_data_dir
    data_dir_writable = _check_dir_writable(data_dir)
    db_file = settings.db_file_path

    return success(
        data={
            "status": "running",
            "service": "AI Companion",
            "version": "0.1.0",
            "database": {
                "ready": _db_ready,
                "path": db_file,
            },
            "data_directory": {
                "path": data_dir,
                "writable": data_dir_writable,
            },
        }
    )


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
