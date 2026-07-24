"""应用全局状态管理。

集中管理应用级共享状态，替代跨模块的全局变量和 setter 函数。
线程安全，避免循环导入。
"""

from __future__ import annotations

from threading import Lock


class AppState:
    """应用全局状态（线程安全单例）。"""

    _instance: AppState | None = None
    _lock: Lock = Lock()

    def __new__(cls) -> AppState:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._state_lock = Lock()
                    instance._db_ready = False
                    instance._db_migration_completed = False
                    instance._task_scheduler: object | None = None
                    cls._instance = instance
        return cls._instance

    # ── 数据库就绪状态 ──

    @property
    def db_ready(self) -> bool:
        with self._state_lock:
            return self._db_ready

    @db_ready.setter
    def db_ready(self, value: bool) -> None:
        with self._state_lock:
            self._db_ready = value

    @property
    def db_migration_completed(self) -> bool:
        with self._state_lock:
            return self._db_migration_completed

    @db_migration_completed.setter
    def db_migration_completed(self, value: bool) -> None:
        with self._state_lock:
            self._db_migration_completed = value

    # ── 后台任务调度器 ──

    @property
    def task_scheduler(self) -> object | None:
        with self._state_lock:
            return self._task_scheduler

    @task_scheduler.setter
    def task_scheduler(self, value: object | None) -> None:
        with self._state_lock:
            self._task_scheduler = value


# 模块级单例（全局唯一入口）
app_state = AppState()
