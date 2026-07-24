"""后台任务轮询调度器。

使用 ThreadPoolExecutor 异步执行任务，LLM 调用不阻塞主循环。
自适轮询间隔：有任务时高频，空闲时指数退避。

关键设计：
- 任务领取和恢复在主循环执行
- 任务执行提交到线程池，不阻塞轮询
- 空闲时轮询间隔从 2s→5s→15s→30s 指数退避
- 检测到新任务后立即恢复高频轮询
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait

from app.core.database import get_background_db_session
from app.services import task as services_task
from app.tasks.executor import execute_task
from app.utils.logger_config import setup_logger

logger = setup_logger(__name__)

# 自适应轮询配置
_POLL_ACTIVE = 1.0       # 有任务时的轮询间隔（秒）
_POLL_IDLE_MIN = 2.0     # 空闲起始间隔（秒）
_POLL_IDLE_MAX = 30.0    # 空闲最大间隔（秒）
_POLL_IDLE_MULTIPLIER = 2.5  # 空闲时每次翻倍

# 线程池配置
_MAX_WORKERS = 4          # 最大并发任务数


class TaskScheduler:
    """后台任务轮询调度器，独立线程 + 线程池异步执行。"""

    def __init__(
        self,
        poll_interval: float = _POLL_ACTIVE,
        recovery_interval: float = 60.0,
        batch_size: int = 10,
    ):
        self.poll_interval = poll_interval
        self.recovery_interval = recovery_interval
        self.batch_size = batch_size
        self._thread: threading.Thread | None = None
        self._recovery_thread: threading.Thread | None = None
        self._running = False
        self._executor = ThreadPoolExecutor(
            max_workers=_MAX_WORKERS,
            thread_name_prefix="task-worker",
        )
        # 上次有任务的时间，用于自适应退避
        self._last_busy_time = time.time()
        # 当前空闲退避间隔
        self._idle_interval = _POLL_IDLE_MIN

    def start(self) -> None:
        """启动调度器。"""
        if self._running:
            logger.warning("调度器已在运行")
            return

        self._running = True
        self._last_busy_time = time.time()

        # 主轮询线程
        self._thread = threading.Thread(
            target=self._loop,
            name="task-scheduler",
            daemon=True,
        )
        self._thread.start()

        # 超时恢复线程（独立周期，不阻塞主循环）
        self._recovery_thread = threading.Thread(
            target=self._recovery_loop,
            name="task-recovery",
            daemon=True,
        )
        self._recovery_thread.start()

        logger.info(
            f"调度器已启动: poll_active={_POLL_ACTIVE}s "
            f"poll_idle={_POLL_IDLE_MIN}~{_POLL_IDLE_MAX}s "
            f"workers={_MAX_WORKERS}",
        )

    def stop(self) -> None:
        """停止调度器。"""
        self._running = False
        self._executor.shutdown(wait=False, cancel_futures=True)
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        if self._recovery_thread:
            self._recovery_thread.join(timeout=5)
            self._recovery_thread = None
        logger.info("调度器已停止")

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    # ── 主轮询循环 ─────────────────────────────────────────────────────

    def _loop(self) -> None:
        """调度器主循环：领取任务 → 提交线程池 → 自适应退避。"""
        while self._running:
            try:
                self._process_pending()
            except Exception as e:
                logger.error(f"轮询异常: {e!s}", exc_info=True)

            # 自适应退避：有任务时高频轮询，空闲时指数退避
            sleep_seconds = self._calc_sleep_interval()
            self._sleep_with_check(sleep_seconds)

    def _process_pending(self) -> None:
        """领取待处理任务并提交到线程池。"""
        with get_background_db_session() as db:
            tasks = services_task.claim_pending_tasks(db, self.batch_size)

        if not tasks:
            return

        # 有任务 → 重置空闲计时器和退避间隔
        self._last_busy_time = time.time()
        self._idle_interval = _POLL_IDLE_MIN

        # 提交到线程池，不阻塞主循环
        for t in tasks:
            if not self._running:
                break
            self._executor.submit(self._run_task_safe, t.id, t.task_type, t.payload)

    def _run_task_safe(self, task_id: int, task_type: str, payload: str | None) -> None:
        """安全执行单个任务（在线程池中运行）。"""
        try:
            execute_task(task_id, task_type, payload)
        except Exception as e:
            logger.error(f"任务异常: id={task_id} type={task_type} error={e!s}")

    # ── 超时恢复循环 ───────────────────────────────────────────────────

    def _recovery_loop(self) -> None:
        """超时恢复循环（独立线程，固定周期）。"""
        while self._running:
            time.sleep(self.recovery_interval)
            if not self._running:
                break
            try:
                self._recover_tasks()
            except Exception as e:
                logger.error(f"任务恢复异常: {e!s}")

    def _recover_tasks(self) -> None:
        """恢复超时未完成的任务。"""
        with get_background_db_session() as db:
            recovered = services_task.recover_stuck_tasks(db)
            if recovered:
                logger.info(f"恢复超时任务: count={recovered}")

    # ── 自适应退避 ─────────────────────────────────────────────────────

    def _calc_sleep_interval(self) -> float:
        """计算下次轮询的等待时间。

        有任务时按高频轮询。
        空闲超过 5 秒后开始指数退避（2s → 5s → 15s → 30s）。
        每次空闲时递增间隔；检测到新任务时由 _process_pending 重置。
        """
        idle_seconds = time.time() - self._last_busy_time

        # 刚有任务（5 秒内），保持高频
        if idle_seconds < 5.0:
            return _POLL_ACTIVE

        # 已空闲：记录当前退避间隔，并为下次递增
        current = self._idle_interval
        self._idle_interval = min(
            current * _POLL_IDLE_MULTIPLIER,
            _POLL_IDLE_MAX,
        )
        return min(current, _POLL_IDLE_MAX)

    def _sleep_with_check(self, seconds: float) -> None:
        """分段 sleep，期间检测退出标志。"""
        chunk = 0.1  # 每 100ms 检查一次退出
        elapsed = 0.0
        while elapsed < seconds and self._running:
            time.sleep(chunk)
            elapsed += chunk
