from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ..cancellation import CancellationToken
from ..com_utils import com_initialized
from ..pairing import PairResult
from ..pipeline import Event, run_pipeline


class CompareWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int, int)         # current, total
    finished_ok = Signal(str)                  # summary path
    failed = Signal(str)

    def __init__(
        self,
        a: Path,
        b: Path,
        out: Path,
        pair_result: PairResult | None = None,
        a_total: int | None = None,
        b_total: int | None = None,
    ) -> None:
        super().__init__()
        self._a = a
        self._b = b
        self._out = out
        self._pair_result = pair_result
        self._a_total = a_total
        self._b_total = b_total
        self.token = CancellationToken()

    def _on_event(self, e: Event) -> None:
        if e.kind == "log":
            self.log_signal.emit(e.message)
        elif e.kind == "progress":
            self.progress_signal.emit(e.current, e.total)

    def run(self) -> None:
        try:
            with com_initialized():
                result = run_pipeline(
                    self._a, self._b, self._out,
                    pair_result=self._pair_result,
                    token=self.token, on_event=self._on_event,
                    a_total=self._a_total, b_total=self._b_total,
                )
            summary = str(result.summary_path) if result.summary_path else ""
            self.finished_ok.emit(summary)
        except Exception as e:
            self.failed.emit(f"{e.__class__.__name__}: {e}")
