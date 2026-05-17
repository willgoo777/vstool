from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..i18n import T
from .worker import CompareWorker


class _PathRow(QWidget):
    def __init__(self, label: str, dialog_title: str, parent=None):
        super().__init__(parent)
        self._dialog_title = dialog_title
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        self.edit = QLineEdit()
        self.btn = QPushButton(T["btn_browse"])
        self.btn.clicked.connect(self._pick)
        lay.addWidget(lbl)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)

    def _pick(self) -> None:
        cur = self.edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, self._dialog_title, cur)
        if chosen:
            self.edit.setText(chosen)

    def value(self) -> str:
        return self.edit.text().strip()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(T["app_title"])
        self.resize(820, 560)

        self.row_a = _PathRow(T["label_folder_a"], T["msg_pick_dir_a"])
        self.row_b = _PathRow(T["label_folder_b"], T["msg_pick_dir_b"])
        self.row_out = _PathRow(T["label_output"], T["msg_pick_output"])

        self.btn_start = QPushButton(T["btn_start"])
        self.btn_start.setDefault(True)
        self.btn_start.clicked.connect(self._on_start)
        self.btn_cancel = QPushButton(T["btn_cancel"])
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_open = QPushButton(T["btn_open_output"])
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._on_open_output)

        action_row = QHBoxLayout()
        action_row.addWidget(self.btn_start)
        action_row.addWidget(self.btn_cancel)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_open)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QTextEdit.NoWrap)

        body = QVBoxLayout()
        body.addWidget(self.row_a)
        body.addWidget(self.row_b)
        body.addWidget(self.row_out)
        body.addLayout(action_row)
        body.addWidget(self.progress)
        body.addWidget(self.log, 1)

        central = QWidget()
        central.setLayout(body)
        self.setCentralWidget(central)

        self.worker: CompareWorker | None = None

    # -- 槽 --

    def _validate(self) -> tuple[Path, Path, Path] | None:
        a = self.row_a.value()
        b = self.row_b.value()
        o = self.row_out.value()
        if not (a and b and o):
            self._warn(T["err_dir_missing"])
            return None
        a_p, b_p, o_p = Path(a), Path(b), Path(o)
        for p in (a_p, b_p):
            if not p.exists() or not p.is_dir():
                self._warn(T["err_dir_not_exist"].format(path=p))
                return None
        if a_p.resolve() == b_p.resolve():
            self._warn(T["err_dir_same"])
            return None
        out_r = o_p.resolve()
        if out_r.is_relative_to(a_p.resolve()) or out_r.is_relative_to(b_p.resolve()):
            self._warn(T["err_output_inside"])
            return None
        return a_p, b_p, o_p

    def _on_start(self) -> None:
        triple = self._validate()
        if triple is None:
            return
        a, b, o = triple
        self.log.clear()
        self.progress.setRange(0, 0)  # 不确定模式直到收到第一次 progress
        self._set_running(True)

        self.worker = CompareWorker(a, b, o)
        self.worker.log_signal.connect(self._append_log)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_finished_ok)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(lambda: self._set_running(False))
        self.worker.start()

    def _on_cancel(self) -> None:
        if self.worker:
            self.worker.token.cancel()
            self.btn_cancel.setEnabled(False)

    def _on_open_output(self) -> None:
        out = self.row_out.value()
        if not out:
            return
        webbrowser.open(Path(out).resolve().as_uri())

    def _on_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            return
        if self.progress.maximum() != total:
            self.progress.setRange(0, total)
        self.progress.setValue(current)

    def _on_finished_ok(self, summary_path: str) -> None:
        self.btn_open.setEnabled(True)
        if summary_path:
            try:
                webbrowser.open(Path(summary_path).as_uri())
            except Exception:
                pass

    def _on_failed(self, msg: str) -> None:
        self._append_log(T["status_failed"].format(msg=msg))
        QMessageBox.critical(self, T["app_title"], msg)

    # -- 工具 --

    def _set_running(self, running: bool) -> None:
        for w in (self.row_a, self.row_b, self.row_out, self.btn_start):
            w.setEnabled(not running)
        self.btn_cancel.setEnabled(running)

    def _append_log(self, text: str) -> None:
        self.log.append(text)
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log.setTextCursor(cursor)

    def _warn(self, msg: str) -> None:
        QMessageBox.warning(self, T["app_title"], msg, QMessageBox.Ok)
