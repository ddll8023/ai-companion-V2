"""目标和任务服务。

职责：
- 目标 CRUD 和进度计算
- 任务 CRUD
- AI 建议生成和用户确认/拒绝
- 关键操作记录审计
"""

from __future__ import annotations

import math

from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models.goal import Goal, Task
from app.schemas.common import ErrorCode, PaginatedResponse, PaginationInfo
from app.schemas.goal import (
    GoalCreate,
    GoalDeleteRequest,
    GoalDetailResponse,
    GoalListQuery,
    GoalResponse,
    GoalUpdate,
    TaskCreate,
    TaskListQuery,
    TaskResponse,
    TaskSuggestionCreate,
    TaskUpdate,
    TaskWithGoalResponse,
    SuggestionStatus,
    TaskStatus,
)
from app.services.audit import record_audit
from app.utils.exception import ServiceException
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


# ── 目标 CRUD ────────────────────────────────────────────────────────────────


def create_goal(db: Session, data: GoalCreate):
    """创建目标。"""
    goal = Goal(
        title=data.title,
        description=data.description,
        target_date=data.target_date,
        status=0,
    )
    db.add(goal)
    commit_or_rollback(db)
    logger.info(f"创建目标: id={goal.id}, title='{data.title}'")

    record_audit(
        db=db,
        action="goal.create",
        target_type="goal",
        target_id=goal.id,
        summary=f"创建目标: {data.title[:100]}",
    )

    return _build_goal_response(db, goal)


def query_goals(db: Session, query: GoalListQuery):
    """查询目标列表。"""
    base_stmt = select(Goal)

    if query.status is not None:
        base_stmt = base_stmt.where(Goal.status == query.status)
    if query.keyword:
        keyword = f"%{query.keyword}%"
        base_stmt = base_stmt.where(
            or_(Goal.title.like(keyword), Goal.description.like(keyword))
        )

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(Goal.created_at))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    # 批量计算所有目标的进度统计数据，避免 N+1
    stats_map = _compute_goal_stats(db, [g.id for g in items])

    return PaginatedResponse(
        lists=[_build_goal_response(db, g, stats_map) for g in items],
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_goal(db: Session, goal_id: int):
    """获取目标详情（含关联任务）。"""
    goal = _get_goal_or_error(db, goal_id)

    tasks = db.scalars(
        select(Task)
        .where(
            and_(
                Task.goal_id == goal_id,
                Task.suggestion_status != SuggestionStatus.REJECTED,
            )
        )
        .order_by(desc(Task.priority), desc(Task.created_at))
    ).all()

    return GoalDetailResponse(
        goal=_build_goal_response(db, goal),
        tasks=[TaskResponse.model_validate(t) for t in tasks],
    )


def update_goal(db: Session, goal_id: int, data: GoalUpdate):
    """更新目标。"""
    goal = _get_goal_or_error(db, goal_id)

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise ServiceException(ErrorCode.PARAM_ERROR, "没有需要更新的字段")

    for key, value in update_data.items():
        setattr(goal, key, value)

    commit_or_rollback(db)
    logger.info(f"更新目标: id={goal_id}")

    record_audit(
        db=db,
        action="goal.update",
        target_type="goal",
        target_id=goal_id,
        summary=f"更新目标: {goal.title[:100]}",
    )

    return _build_goal_response(db, goal)


def delete_goal(db: Session, goal_id: int, data: GoalDeleteRequest):
    """删除目标。

    根据 task_action 处理关联任务：
    - unlink: 解除关联（goal_id 置 NULL）
    - cascade: 级联删除
    """
    goal = _get_goal_or_error(db, goal_id)

    if data.task_action == "cascade":
        # 级联删除关联任务
        tasks = db.scalars(
            select(Task).where(Task.goal_id == goal_id)
        ).all()
        for t in tasks:
            db.delete(t)
        db.flush()

    elif data.task_action == "unlink":
        # 解除关联：将关联任务的 goal_id 置为 NULL
        tasks = db.scalars(
            select(Task).where(Task.goal_id == goal_id)
        ).all()
        for t in tasks:
            t.goal_id = None
        db.flush()

    record_audit(
        db=db,
        action="goal.delete",
        target_type="goal",
        target_id=goal_id,
        summary=f"删除目标: {goal.title[:100]}, task_action={data.task_action}",
    )

    db.delete(goal)
    commit_or_rollback(db)
    logger.info(f"删除目标: id={goal_id}")

    return {"id": goal_id}


# ── 任务 CRUD ────────────────────────────────────────────────────────────────


def create_task(db: Session, data: TaskCreate):
    """创建任务（手动创建）。"""
    if data.goal_id:
        goal = db.get(Goal, data.goal_id)
        if not goal:
            raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"目标不存在: {data.goal_id}")

    task = Task(
        goal_id=data.goal_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        status=0,
        is_from_suggestion=0,
        suggestion_status=SuggestionStatus.NONE,
    )
    db.add(task)
    commit_or_rollback(db)
    logger.info(f"创建任务: id={task.id}, title='{data.title}'")

    record_audit(
        db=db,
        action="task.create",
        target_type="task",
        target_id=task.id,
        summary=f"创建任务: {data.title[:100]}",
    )

    return TaskResponse.model_validate(task)


def query_tasks(
    db: Session,
    query: TaskListQuery,
) -> PaginatedResponse[TaskWithGoalResponse]:
    """查询任务列表（含关联目标信息）。"""
    base_stmt = select(Task)

    if query.goal_id is not None:
        base_stmt = base_stmt.where(Task.goal_id == query.goal_id)
    if query.status is not None:
        base_stmt = base_stmt.where(Task.status == query.status)
    if query.suggestion_status is not None:
        base_stmt = base_stmt.where(Task.suggestion_status == query.suggestion_status)
    if query.is_suggestion is not None:
        base_stmt = base_stmt.where(Task.is_from_suggestion == query.is_suggestion)
    if query.keyword:
        keyword = f"%{query.keyword}%"
        base_stmt = base_stmt.where(Task.title.like(keyword))

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    items = (
        db.scalars(
            base_stmt
            .order_by(desc(Task.priority), desc(Task.created_at))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
    )

    # 批量获取关联目标标题，避免 N+1
    goal_ids = {t.goal_id for t in items if t.goal_id}
    goals_map = {}
    if goal_ids:
        goal_entities = db.scalars(select(Goal).where(Goal.id.in_(goal_ids))).all()
        goals_map = {g.id: g.title for g in goal_entities}

    # 构建含目标标题的响应
    response_list = []
    for task in items:
        goal_title = goals_map.get(task.goal_id) if task.goal_id else None
        task_resp = TaskWithGoalResponse(
            id=task.id,
            goal_id=task.goal_id,
            goal_title=goal_title,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            is_from_suggestion=task.is_from_suggestion,
            suggestion_status=task.suggestion_status,
            suggestion_data=task.suggestion_data,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        response_list.append(task_resp)

    return PaginatedResponse(
        lists=response_list,
        pagination=PaginationInfo(
            page=query.page,
            page_size=query.page_size,
            total=total or 0,
            total_pages=math.ceil((total or 0) / query.page_size),
        ),
    )


def get_task(db: Session, task_id: int):
    """获取任务详情。"""
    task = _get_task_or_error(db, task_id)

    goal_title = None
    if task.goal_id:
        goal = db.get(Goal, task.goal_id)
        if goal:
            goal_title = goal.title

    return TaskWithGoalResponse(
        id=task.id,
        goal_id=task.goal_id,
        goal_title=goal_title,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        is_from_suggestion=task.is_from_suggestion,
        suggestion_status=task.suggestion_status,
        suggestion_data=task.suggestion_data,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def update_task(db: Session, task_id: int, data: TaskUpdate):
    """更新任务。"""
    task = _get_task_or_error(db, task_id)

    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise ServiceException(ErrorCode.PARAM_ERROR, "没有需要更新的字段")

    # 校验 goal_id 有效性
    if "goal_id" in update_data and update_data["goal_id"] is not None:
        goal = db.get(Goal, update_data["goal_id"])
        if not goal:
            raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"目标不存在: {update_data['goal_id']}")

    for key, value in update_data.items():
        setattr(task, key, value)

    commit_or_rollback(db)
    logger.info(f"更新任务: id={task_id}")

    record_audit(
        db=db,
        action="task.update",
        target_type="task",
        target_id=task_id,
        summary=f"更新任务: {task.title[:100]}",
    )

    return TaskResponse.model_validate(task)


def delete_task(db: Session, task_id: int):
    """删除任务（硬删除）。"""
    task = _get_task_or_error(db, task_id)

    record_audit(
        db=db,
        action="task.delete",
        target_type="task",
        target_id=task_id,
        summary=f"删除任务: {task.title[:100]}",
    )

    db.delete(task)
    commit_or_rollback(db)
    logger.info(f"删除任务: id={task_id}")

    return {"id": task_id}


# ── AI 建议管理 ──────────────────────────────────────────────────────────────


def create_suggestion(db: Session, data: TaskSuggestionCreate):
    """创建 AI 建议任务。"""
    task = Task(
        goal_id=None,
        title=data.title,
        description=data.description,
        priority=data.priority,
        status=TaskStatus.PENDING,
        is_from_suggestion=1,
        suggestion_status=SuggestionStatus.PENDING,
        suggestion_data=data.suggestion_data,
    )
    db.add(task)
    commit_or_rollback(db)
    logger.info(f"创建 AI 建议: id={task.id}, title='{data.title}'")

    record_audit(
        db=db,
        action="task.suggestion.create",
        target_type="task",
        target_id=task.id,
        summary=f"AI 建议任务: {data.title[:100]}",
    )

    return TaskResponse.model_validate(task)


def accept_suggestion(db: Session, task_id: int):
    """接受 AI 建议。

    将建议状态更新为 accepted，任务正式生效。
    """
    task = _get_task_or_error(db, task_id)

    if task.suggestion_status != SuggestionStatus.PENDING:
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"仅可接受待确认的建议，当前建议状态: {task.suggestion_status}",
        )

    task.suggestion_status = SuggestionStatus.ACCEPTED
    task.status = TaskStatus.PENDING
    commit_or_rollback(db)
    logger.info(f"接受 AI 建议: id={task_id}")

    record_audit(
        db=db,
        action="task.suggestion.accept",
        target_type="task",
        target_id=task_id,
        summary=f"接受 AI 建议任务: {task.title[:100]}",
    )

    return TaskResponse.model_validate(task)


def reject_suggestion(db: Session, task_id: int):
    """拒绝 AI 建议。

    标记为 rejected，后续不再作为正式任务引用。
    """
    task = _get_task_or_error(db, task_id)

    if task.suggestion_status != SuggestionStatus.PENDING:
        raise ServiceException(
            ErrorCode.PARAM_ERROR,
            f"仅可拒绝待确认的建议，当前建议状态: {task.suggestion_status}",
        )

    task.suggestion_status = SuggestionStatus.REJECTED
    commit_or_rollback(db)
    logger.info(f"拒绝 AI 建议: id={task_id}")

    record_audit(
        db=db,
        action="task.suggestion.reject",
        target_type="task",
        target_id=task_id,
        summary=f"拒绝 AI 建议任务: {task.title[:100]}",
    )

    return TaskResponse.model_validate(task)


# ── 对话引用 ──────────────────────────────────────────────────────────────────


def query_active_goals_for_chat(db: Session):
    """查询有效的目标列表（供对话上下文使用）。

    只返回状态为 active 的目标。
    """
    items = db.scalars(
        select(Goal)
        .where(Goal.status == 0)
        .order_by(desc(Goal.created_at))
    ).all()

    stats_map = _compute_goal_stats(db, [g.id for g in items])
    return [_build_goal_response(db, g, stats_map) for g in items]


def query_active_tasks_for_chat(db: Session, goal_id: int | None = None):
    """查询有效的任务列表（供对话上下文使用）。

    只返回已接受的任务（非建议、已接受的建议）。
    """
    base_stmt = select(Task).where(
        and_(
            Task.suggestion_status != SuggestionStatus.REJECTED,
            Task.status != TaskStatus.ABANDONED,
        )
    )
    if goal_id is not None:
        base_stmt = base_stmt.where(Task.goal_id == goal_id)

    items = db.scalars(
        base_stmt.order_by(desc(Task.priority), desc(Task.created_at))
    ).all()

    return [TaskResponse.model_validate(t) for t in items]


"""辅助函数"""


def _compute_goal_stats(db: Session, goal_ids: list[int]) -> dict[int, tuple[int, int]]:
    """批量计算目标的任务进度统计数据。

    返回 {goal_id: (total, completed)} 映射。
    """
    if not goal_ids:
        return {}

    rows = db.execute(
        select(
            Task.goal_id,
            func.count().label("total"),
            func.sum(case((Task.status == TaskStatus.COMPLETED, 1), else_=0)).label("completed"),
        ).where(
            and_(
                Task.goal_id.in_(goal_ids),
                Task.suggestion_status != SuggestionStatus.REJECTED,
            )
        ).group_by(Task.goal_id)
    ).all()

    return {row.goal_id: (row.total, row.completed) for row in rows}


def _get_goal_or_error(db: Session, goal_id: int):
    """获取目标实体，不存在时抛出异常。"""
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"目标不存在: {goal_id}")
    return goal


def _get_task_or_error(db: Session, task_id: int):
    """获取任务实体，不存在时抛出异常。"""
    task = db.get(Task, task_id)
    if task is None:
        raise ServiceException(ErrorCode.DATA_NOT_FOUND, f"任务不存在: {task_id}")
    return task


def _build_goal_response(
    db: Session,
    goal: Goal,
    stats_map: dict[int, tuple[int, int]] | None = None,
):
    """构建目标响应（含进度计算）。

    进度 = 已完成任务数 / 非拒绝状态的任务总数 * 100
    支持通过 stats_map 避免 N+1 查询。
    """
    if stats_map and goal.id in stats_map:
        total, completed = stats_map[goal.id]
    else:
        total = db.scalar(
            select(func.count())
            .where(
                and_(
                    Task.goal_id == goal.id,
                    Task.suggestion_status != SuggestionStatus.REJECTED,
                )
            )
        ) or 0

        completed = db.scalar(
            select(func.count())
            .where(
                and_(
                    Task.goal_id == goal.id,
                    Task.status == TaskStatus.COMPLETED,
                    Task.suggestion_status != SuggestionStatus.REJECTED,
                )
            )
        ) or 0

    progress = int((completed / total) * 100) if total > 0 else 0

    return GoalResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        status=goal.status,
        target_date=goal.target_date,
        progress=progress,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )
