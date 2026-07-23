"""简单轮询调度器。

使用 threading.Thread 运行轮询循环，守护线程，应用退出时自动结束。
"""

from __future__ import annotations

import threading
import time

from app.core.database import get_background_db_session
from app.services import task as services_task
from app.tasks.executor import execute_task
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)


class TaskScheduler:
    """后台任务轮询调度器，独立线程定时轮询待处理任务。"""

    def __init__(
        self,
        poll_interval: float = 2.0,
        recovery_interval: float = 60.0,
        batch_size: int = 10,
    ):
        self.poll_interval = poll_interval
        self.recovery_interval = recovery_interval
        self.batch_size = batch_size
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """启动调度器。"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            name="task-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"后台任务调度器已启动: poll={self.poll_interval}s recovery={self.recovery_interval}s")

    def stop(self) -> None:
        """停止调度器。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("后台任务调度器已停止")

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    def _loop(self) -> None:
        """调度器主循环。"""
        last_recovery_time = 0.0

        while self._running:
            try:
                now = time.time()
                if now - last_recovery_time >= self.recovery_interval:
                    self._recover_tasks()
                    last_recovery_time = now

                self._process_pending()
            except Exception as e:
                logger.error(f"调度器循环异常: {e!s}", exc_info=True)

            time.sleep(self.poll_interval)

    def _process_pending(self) -> None:
        """领取并执行待处理任务。"""
        with get_background_db_session() as db:
            tasks = services_task.claim_pending_tasks(db, self.batch_size)

        for t in tasks:
            if not self._running:
                break
            execute_task(t.id, t.task_type, t.payload)

    def _recover_tasks(self) -> None:
        """恢复超时未完成的任务。"""
        with get_background_db_session() as db:
            recovered = services_task.recover_stuck_tasks(db)
            if recovered:
                logger.info(f"恢复超时任务数: {recovered}")
