from __future__ import annotations

import threading


class CancellationToken:
    """线程安全的取消标志。GUI 主线程置位，worker 在每对之间检查。"""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise OperationCancelled()


class OperationCancelled(Exception):
    """pipeline 检测到取消时主动抛出，外层捕获后写汇总并退出。"""
