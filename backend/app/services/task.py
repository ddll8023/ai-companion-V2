"""后台任务服务。

职责：
- 创建任务（含去重检查）
- 排他领取待处理任务
- 更新任务状态
- 查询任务列表
- 取消任务
- 超时任务恢复

关键设计：
- 排他领取：使用 UPDATE ... WHERE status='pending' 通过 SQLite 事务锁实现
- 去重：dedup_key + task_type + 未终态任务检查
- 超时恢复：检查长时间处于 processing 状态的任务
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, func, select, text, update
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.task import BackgroundTask
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.task import TaskCreate, TaskQueryRequest, TaskResponse
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 任务超时时间（秒）
_TASK_TIMEOUT_SECONDS = 300

# 轮询时每次领取的最大任务数
_CLAIM_BATCH_SIZE = 10

# ── 公共入口函数 ────────────────────────────────────────────────────────


def create_task(db: Session, data: TaskCreate) -> TaskResponse:
    """创建后台任务。"""
    if data.dedup_key:
        existing = _find_duplicate(db, data.task_type, data.dedup_key)
        if existing is not None:
            logger.info(f"任务已存在，跳过创建: type={data.task_type} dedup_key={data.dedup_key}")
            return TaskResponse.model_validate(existing)

    task = BackgroundTask(
        task_type=data.task_type,
        status="pending",
        payload=data.payload,
        dedup_key=data.dedup_key,
        priority=data.priority,
        max_retries=data.max_retries,
        source_version=data.source_version,
        scheduled_at=data.scheduled_at or datetime.now(),
    )
    db.add(task)
    commit_or_rollback(db)
    logger.info(f"创建后台任务: id={task.id} type={data.task_type}")

    record_audit(
        db=db,
        action="task.create",
        target_type="task",
        target_id=task.id,
        summary=f"创建后台任务: {data.task_type}",
    )

    return TaskResponse.model_validate(task)


def claim_pending_tasks(db: Session, batch_size: int = _CLAIM_BATCH_SIZE) -> list[BackgroundTask]:
    """原子领取待处理或待重试的任务。

    使用单条 UPDATE + 子查询原子操作，避免并发领取同一任务。
    """
    now = datetime.now()

    # 原子 UPDATE：子查询选取 → UPDATE 状态
    # retry_count 仅在 status='retrying'（重试领取）时递增
    # 首次领取（status='pending'）不递增，保证有效重试次数 = max_retries
    db.execute(
        text("""
            UPDATE background_tasks
            SET status = 'processing',
                started_at = :now,
                retry_count = CASE
                    WHEN status = 'retrying' THEN retry_count + 1
                    ELSE retry_count
                END
            WHERE id IN (
                SELECT id FROM background_tasks
                WHERE status IN ('pending', 'retrying')
                  AND scheduled_at <= :now
                ORDER BY priority DESC, id ASC
                LIMIT :limit
            )
        """),
        {"now": now, "limit": batch_size},
    )
    commit_or_rollback(db)

    # 重新查询已被标记为 processing 的任务（刚被 UPDATE 的）
    claimed = list(
        db.scalars(
            select(BackgroundTask)
            .where(
                BackgroundTask.status == "processing",
                BackgroundTask.started_at >= now,
                BackgroundTask.scheduled_at <= now,
            )
            .order_by(BackgroundTask.id)
            .limit(batch_size)
        ).all()
    )

    for t in claimed:
        logger.info(f"领取任务: id={t.id} type={t.task_type} retry={t.retry_count}")

    return claimed


def complete_task(db: Session, task_id: int, result: str | None = None) -> None:
    """标记任务为已完成。"""
    task = db.get(BackgroundTask, task_id)
    if task is None:
        logger.warning(f"任务不存在，无法标记完成: id={task_id}")
        return
    task.status = "completed"
    task.result = result
    task.completed_at = datetime.now()
    commit_or_rollback(db)
    logger.info(f"任务完成: id={task_id} type={task.task_type}")


def fail_task(db: Session, task_id: int, error_message: str, should_retry: bool = True) -> None:
    """标记任务为失败（进入待重试或直接失败）。"""
    task = db.get(BackgroundTask, task_id)
    if task is None:
        logger.warning(f"任务不存在，无法标记失败: id={task_id}")
        return

    task.error_message = error_message[:512]

    if should_retry and task.retry_count < task.max_retries:
        task.status = "retrying"
        backoff_seconds = min(2 ** task.retry_count, 300)
        task.scheduled_at = datetime.now() + timedelta(seconds=backoff_seconds)
        logger.info(f"任务进入待重试: id={task_id} retry={task.retry_count}/{task.max_retries} backoff={backoff_seconds}s")
    else:
        task.status = "failed"
        task.completed_at = datetime.now()
        logger.info(f"任务已失败: id={task_id} retry={task.retry_count}/{task.max_retries}")

    commit_or_rollback(db)


def cancel_task(db: Session, task_id: int) -> TaskResponse:
    """取消指定任务。"""
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"任务不存在: {task_id}")

    if task.status not in ("pending", "retrying"):
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"无法取消状态为 '{task.status}' 的任务，仅可取消待处理或待重试的任务",
        )

    task.status = "cancelled"
    task.completed_at = datetime.now()
    commit_or_rollback(db)
    logger.info(f"任务已取消: id={task_id} type={task.task_type}")

    return TaskResponse.model_validate(task)


def recover_stuck_tasks(db: Session, timeout_seconds: int = _TASK_TIMEOUT_SECONDS) -> int:
    """恢复超时未完成的 processing 任务。"""
    timeout_threshold = datetime.now() - timedelta(seconds=timeout_seconds)

    result = db.execute(
        update(BackgroundTask)
        .where(
            and_(
                BackgroundTask.status == "processing",
                BackgroundTask.started_at <= timeout_threshold,
            )
        )
        .values(
            status="retrying",
            error_message="任务执行超时，已自动恢复",
        )
    )

    if result.rowcount == 0:
        return 0

    commit_or_rollback(db)
    logger.info(f"恢复超时任务: count={result.rowcount}")
    return result.rowcount


def query_tasks(db: Session, query: TaskQueryRequest) -> PaginatedResponse[TaskResponse]:
    """查询任务列表。"""
    base_stmt = select(BackgroundTask)

    if query.task_type:
        base_stmt = base_stmt.where(BackgroundTask.task_type == query.task_type)
    if query.status:
        base_stmt = base_stmt.where(BackgroundTask.status == query.status)

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(BackgroundTask.priority), desc(BackgroundTask.id))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    return PaginatedResponse(
        lists=[TaskResponse.model_validate(item) for item in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_task(db: Session, task_id: int) -> TaskResponse:
    """获取单个任务详情。"""
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"任务不存在: {task_id}")
    return TaskResponse.model_validate(task)


def get_pending_count(db: Session) -> int:
    """获取待处理和待重试的任务数量。"""
    return db.scalar(
        select(func.count()).select_from(
            select(BackgroundTask)
            .where(BackgroundTask.status.in_(["pending", "retrying"]))
            .subquery()
        )
    ) or 0


"""辅助函数"""


def _find_duplicate(db: Session, task_type: str, dedup_key: str) -> BackgroundTask | None:
    """查找同一类型下具有相同去重键且未处于终态的任务。"""
    return db.scalar(
        select(BackgroundTask).where(
            and_(
                BackgroundTask.task_type == task_type,
                BackgroundTask.dedup_key == dedup_key,
                BackgroundTask.status.notin_(["completed", "failed", "cancelled"]),
            )
        ).limit(1)
    )


def get_task_entity(db: Session, task_id: int) -> BackgroundTask:
    """获取任务实体对象（供调度器/执行器内部使用）。"""
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"任务不存在: {task_id}")
    return task
