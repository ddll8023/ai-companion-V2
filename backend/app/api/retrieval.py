"""记忆检索 API 路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.response import error, success
from app.schemas.retrieval import Fts5Status, MemoryContext
from app.services import retrieval as services_retrieval
from app.services.embedding import get_embedding_dimension
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/retrieval", tags=["检索"])


@router.get("/status", response_model=ApiResponse[dict])
def get_fts5_status(
    db: Annotated[Session, Depends(get_db)],
):
    """获取检索索引状态（FTS5 + 向量）。

    用于前端系统状态页面展示全文索引和向量索引状态。
    """
    try:
        fts5 = services_retrieval.check_fts5_available(db)

        # 嵌入向量状态（非阻塞检查）
        vector_available = False
        vector_count = 0
        try:
            from app.models.memory import Memory
            vector_count = db.query(Memory).filter(
                Memory.embedding.isnot(None),
                Memory.status.in_(["confirmed", "corrected"]),
            ).count()
            vector_available = True
        except Exception:
            vector_available = False
            logger.warning("向量嵌入状态检查失败（检索功能降级）")

        return success(data={
            "fts5": fts5,
            "vector": {
                "available": vector_available,
                "memory_count": vector_count,
                "dimension": get_embedding_dimension(),
            },
        })
    except ServiceException as e:
        return error(message=e.message)
