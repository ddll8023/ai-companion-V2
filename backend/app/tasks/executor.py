"""任务执行器。

根据 task_type 查找注册的处理器并执行。由调度器在领取任务后调用。
"""

from __future__ import annotations

import json

from app.core.database import get_background_db_session
from app.services import task as services_task
from app.tasks.registry import get_handler
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


def execute_task(task_id: int, task_type: str, payload: str | None) -> None:
    """执行后台任务。

    Args:
        task_id: 任务 ID
        task_type: 任务类型，用于查找处理器
        payload: 任务参数字符串（JSON），可为 None
    """
    handler = get_handler(task_type)
    if handler is None:
        with get_background_db_session() as db:
            services_task.fail_task(
                db, task_id,
                f"未注册的任务处理器: {task_type}",
                should_retry=False,
            )
        return

    parsed, ok = _parse_payload(task_id, payload)
    if not ok:
        return

    try:
        result = handler(parsed)
        if isinstance(result, str):
            result_str = result
        elif result is not None:
            result_str = json.dumps(result, ensure_ascii=False)
        else:
            result_str = None
        with get_background_db_session() as db:
            services_task.complete_task(db, task_id, result_str)
    except Exception as e:
        logger.error(f"任务执行异常: id={task_id} type={task_type} error={e!s}", exc_info=True)
        with get_background_db_session() as db:
            services_task.fail_task(
                db, task_id,
                str(e)[:512],
                should_retry=True,
            )


"""辅助函数"""


def _parse_payload(task_id: int, payload_str: str | None) -> tuple[dict | None, bool]:
    """解析任务参数字符串。

    Returns:
        (parsed, ok):
        - parsed: 解析后的参数字典，payload 为 None 时也返回 None
        - ok: True 表示可继续执行，False 表示解析失败不应继续
    """
    if payload_str is None:
        return None, True  # 无 payload 是合法的

    try:
        return json.loads(payload_str), True
    except json.JSONDecodeError as e:
        with get_background_db_session() as db:
            services_task.fail_task(
                db, task_id,
                f"任务参数解析失败: {e!s}",
                should_retry=False,
            )
        return None, False
