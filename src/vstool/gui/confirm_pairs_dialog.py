"""配对确认对话框。

在主线程同步跑完 scan + fuzzy_pair 后弹出，允许用户：
- 切换某个配对的 B 侧文件（从当前 only_b 池里选）；
- 移除某个配对（A、B 各自回到 only_a / only_b 池）；
- 从孤立文件池里手动新增配对。

确认后通过 result_pair_result() 返回编辑后的 PairResult。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import T
from ..pairing import (
    MATCH_EXACT,
    MATCH_FUZZY,
    MATCH_MANUAL,
    FilePair,
    PairResult,
    repair,
)
from ..scanner import ScannedFile


_BG_BY_MATCH = {
    MATCH_EXACT: "#E6F4EA",   # 浅绿
    MATCH_FUZZY: "#FFF4D6",   # 浅黄
    MATCH_MANUAL: "#E1ECF7",  # 浅蓝
}


@dataclass
class _Row:
    a_key: str
    b_key: str
    match_type: str
    score: float


class ConfirmPairsDialog(QDialog):
    def __init__(
        self,
        pair_result: PairResult,
        a_map: dict[str, ScannedFile],
        b_map: dict[str, ScannedFile],
        a_dir: Path,
        b_dir: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(T["confirm_title"])
        self.resize(900, 640)

        self._a_map = a_map
        self._b_map = b_map
        self._a_dir = Path(a_dir).resolve()
        self._b_dir = Path(b_dir).resolve()

        # 当前编辑状态：所有配对 + 当前 orphans
        self._rows: list[_Row] = [
            _Row(
                a_key=self._key_for_path(p.a_path, a_map),
                b_key=p.key,
                match_type=p.match_type,
                score=p.score,
            )
            for p in pair_result.pairs
        ]
        self._only_a: set[str] = {sf.relpath.lower() for sf in pair_result.only_a}
        self._only_b: set[str] = {sf.relpath.lower() for sf in pair_result.only_b}

        # ---- UI ----
        intro = QLabel(T["confirm_intro"])
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 14px; padding: 8px;")

        header = QHBoxLayout()
        h_a = self._make_dir_header("A", self._a_dir)
        h_b = self._make_dir_header("B", self._b_dir)
        header.addWidget(h_a, 1)
        header.addSpacing(40)  # "vs" 列宽
        header.addWidget(h_b, 1)
        header.addSpacing(40)  # 操作列宽

        # 滚动区
        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        self._rows_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._rows_container)

        # 孤立文件折叠区 + 添加按钮
        self._only_a_label = QLabel()
        self._only_b_label = QLabel()
        for lbl in (self._only_a_label, self._only_b_label):
            lbl.setStyleSheet("color: #666; padding: 2px 4px;")
            lbl.setWordWrap(True)

        btn_add = QPushButton(T["confirm_add_pair"])
        btn_add.clicked.connect(self._on_add_pair)

        orphan_row = QHBoxLayout()
        orphan_box = QVBoxLayout()
        orphan_box.addWidget(self._only_a_label)
        orphan_box.addWidget(self._only_b_label)
        orphan_row.addLayout(orphan_box, 1)
        orphan_row.addWidget(btn_add, 0, Qt.AlignTop)

        # 底部按钮
        btns = QDialogButtonBox()
        self._btn_submit = QPushButton(T["confirm_submit"])
        self._btn_submit.setDefault(True)
        self._btn_submit.clicked.connect(self._on_submit)
        btn_cancel = QPushButton(T["confirm_cancel"])
        btn_cancel.clicked.connect(self.reject)
        btns.addButton(btn_cancel, QDialogButtonBox.RejectRole)
        btns.addButton(self._btn_submit, QDialogButtonBox.AcceptRole)

        body = QVBoxLayout(self)
        body.addWidget(intro)
        body.addLayout(header)
        body.addWidget(scroll, 1)
        body.addWidget(_hline())
        body.addLayout(orphan_row)
        body.addWidget(btns)

        self._rebuild_rows()

    # ---------- 对外 ----------

    def result_pair_result(self) -> PairResult:
        """把用户编辑后的状态导出为 PairResult（全部走 repair，标 MATCH_MANUAL）。

        注意：repair 会把所有 pair 标成 manual。如果需要保留 exact/fuzzy 标签，
        可以在此基础上按 _Row.match_type 再覆盖一遍。
        """
        manual = [(r.a_key, r.b_key) for r in self._rows]
        pr = repair(self._a_map, self._b_map, manual)
        # 保留原 match_type / score（FilePair 是 frozen dataclass，需要重建）
        type_by_b = {r.b_key: (r.match_type, r.score) for r in self._rows}
        restored: list[FilePair] = []
        for p in pr.pairs:
            mt, sc = type_by_b.get(p.key, (MATCH_MANUAL, 1.0))
            restored.append(
                FilePair(
                    key=p.key, relpath=p.relpath, ext=p.ext,
                    a_path=p.a_path, b_path=p.b_path,
                    match_type=mt, score=sc,
                )
            )
        return PairResult(pairs=restored, only_a=pr.only_a, only_b=pr.only_b)

    # ---------- 槽 ----------

    def _on_submit(self) -> None:
        if not self._rows:
            QMessageBox.warning(
                self, T["confirm_title"], T["confirm_empty_pairs"]
            )
            return
        self.accept()

    def _on_change_b(self, row_idx: int, new_b_key: str | None) -> None:
        row = self._rows[row_idx]
        if new_b_key is None:
            # 解散此配对
            self._only_a.add(row.a_key)
            self._only_b.add(row.b_key)
            self._rows.pop(row_idx)
        else:
            if new_b_key == row.b_key:
                return
            self._only_b.discard(new_b_key)
            self._only_b.add(row.b_key)
            row.b_key = new_b_key
            row.match_type = MATCH_MANUAL
            row.score = 1.0
        self._rebuild_rows()

    def _on_remove_row(self, row_idx: int) -> None:
        self._on_change_b(row_idx, None)

    def _on_add_pair(self) -> None:
        if not self._only_a or not self._only_b:
            QMessageBox.information(
                self, T["confirm_title"], T["confirm_add_dialog_no_orphans"]
            )
            return
        dlg = _AddPairDialog(
            sorted(self._only_a, key=lambda k: self._a_map[k].relpath.lower()),
            sorted(self._only_b, key=lambda k: self._b_map[k].relpath.lower()),
            self._a_map, self._b_map, self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        ak, bk = dlg.selection()
        self._only_a.discard(ak)
        self._only_b.discard(bk)
        self._rows.append(_Row(ak, bk, MATCH_MANUAL, 1.0))
        self._rebuild_rows()

    # ---------- 渲染 ----------

    def _rebuild_rows(self) -> None:
        # 清空旧行（保留末尾的 stretch）
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        # 按 B 路径稳定排序
        order = sorted(
            range(len(self._rows)),
            key=lambda i: self._b_map[self._rows[i].b_key].relpath.lower(),
        )
        # 重排底层数据让索引与显示一致
        self._rows = [self._rows[i] for i in order]

        for i, row in enumerate(self._rows):
            w = self._build_pair_widget(i, row)
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, w)

        self._refresh_orphan_labels()

    def _build_pair_widget(self, idx: int, row: _Row) -> QWidget:
        a_sf = self._a_map[row.a_key]
        b_sf = self._b_map[row.b_key]

        wrap = QFrame()
        wrap.setObjectName("pairRow")
        bg = _BG_BY_MATCH.get(row.match_type, "#FFFFFF")
        wrap.setStyleSheet(
            f"#pairRow {{ background: {bg}; border: 1px solid #DDD;"
            f" border-radius: 6px; padding: 6px; }}"
        )
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(8, 4, 8, 4)

        a_lbl = QLabel(a_sf.relpath)
        a_lbl.setToolTip(str(a_sf.abspath))
        a_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        a_lbl.setWordWrap(True)

        vs = QLabel("vs")
        vs.setStyleSheet("color: #888; font-weight: bold;")
        vs.setFixedWidth(28)
        vs.setAlignment(Qt.AlignCenter)

        b_btn = QToolButton()
        b_btn.setText(b_sf.relpath)
        b_btn.setToolTip(T["confirm_change_b_tip"])
        b_btn.setPopupMode(QToolButton.InstantPopup)
        b_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        b_btn.setStyleSheet(
            "QToolButton { background: white; border: 1px solid #BBB;"
            " border-radius: 4px; padding: 4px 8px; text-align: left; }"
            "QToolButton::menu-indicator { width: 0px; }"
        )
        b_btn.setMenu(self._build_b_menu(idx, row.b_key))

        match_tag = QLabel(_match_label(row))
        match_tag.setFixedWidth(80)
        match_tag.setAlignment(Qt.AlignCenter)
        match_tag.setStyleSheet(
            "color: #444; font-size: 11px;"
            " border: 1px solid #CCC; border-radius: 4px; padding: 2px 4px;"
        )

        remove = QToolButton()
        remove.setText(T["confirm_remove_pair"])
        remove.setToolTip(T["confirm_remove_pair_tip"])
        remove.setFixedWidth(28)
        remove.clicked.connect(lambda _=False, i=idx: self._on_remove_row(i))

        lay.addWidget(a_lbl, 1)
        lay.addWidget(vs)
        lay.addWidget(b_btn, 1)
        lay.addWidget(match_tag)
        lay.addWidget(remove)
        return wrap

    def _build_b_menu(self, row_idx: int, current_b: str) -> QMenu:
        menu = QMenu(self)
        # 候选 = 当前 B + 全部 only_b
        candidates = sorted(
            {current_b} | self._only_b,
            key=lambda k: self._b_map[k].relpath.lower(),
        )
        for bk in candidates:
            label = self._b_map[bk].relpath
            if bk == current_b:
                label = f"● {label}"
            act = menu.addAction(label)
            act.triggered.connect(
                lambda _=False, i=row_idx, k=bk: self._on_change_b(i, k)
            )
        menu.addSeparator()
        act = menu.addAction(T["confirm_unpair_option"])
        act.triggered.connect(lambda _=False, i=row_idx: self._on_change_b(i, None))
        return menu

    def _refresh_orphan_labels(self) -> None:
        a_names = ", ".join(
            self._a_map[k].relpath
            for k in sorted(self._only_a, key=lambda k: self._a_map[k].relpath.lower())
        )
        b_names = ", ".join(
            self._b_map[k].relpath
            for k in sorted(self._only_b, key=lambda k: self._b_map[k].relpath.lower())
        )
        self._only_a_label.setText(
            T["confirm_only_a"].format(n=len(self._only_a))
            + (f"  —  {a_names}" if a_names else "")
        )
        self._only_b_label.setText(
            T["confirm_only_b"].format(n=len(self._only_b))
            + (f"  —  {b_names}" if b_names else "")
        )

    # ---------- 工具 ----------

    def _make_dir_header(self, side: str, path: Path) -> QPushButton:
        """表头：显示「side: 目录名」，点击在系统文件管理器里打开该目录。"""
        btn = QPushButton(f"{side}：{path.name or str(path)}")
        btn.setToolTip(T["confirm_open_dir_tip"].format(path=path))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFlat(True)
        btn.setStyleSheet(
            "QPushButton { font-weight: bold; color: #1A73E8;"
            " text-decoration: underline; padding: 4px 8px; border: none;"
            " background: transparent; }"
            "QPushButton:hover { color: #0B57D0; }"
        )
        btn.clicked.connect(lambda _=False, p=path: self._open_dir(p))
        return btn

    @staticmethod
    def _open_dir(path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @staticmethod
    def _key_for_path(p, a_map: dict[str, ScannedFile]) -> str:
        for k, sf in a_map.items():
            if sf.abspath == p:
                return k
        # fallback：理论不会走到
        return str(p).lower()


class _AddPairDialog(QDialog):
    """从 only_a / only_b 各选一个文件组成新配对。"""

    def __init__(
        self,
        a_keys: list[str],
        b_keys: list[str],
        a_map: dict[str, ScannedFile],
        b_map: dict[str, ScannedFile],
        parent,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(T["confirm_add_dialog_title"])
        self.resize(520, 180)

        self._a_combo = QComboBox()
        for k in a_keys:
            self._a_combo.addItem(a_map[k].relpath, userData=k)
        self._b_combo = QComboBox()
        for k in b_keys:
            self._b_combo.addItem(b_map[k].relpath, userData=k)

        form = QFormLayout()
        form.addRow(T["confirm_add_dialog_a"], self._a_combo)
        form.addRow(T["confirm_add_dialog_b"], self._b_combo)

        btns = QDialogButtonBox()
        ok = QPushButton(T["confirm_add_dialog_ok"])
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton(T["confirm_cancel"])
        cancel.clicked.connect(self.reject)
        btns.addButton(cancel, QDialogButtonBox.RejectRole)
        btns.addButton(ok, QDialogButtonBox.AcceptRole)

        body = QVBoxLayout(self)
        body.addLayout(form)
        body.addWidget(btns)

    def selection(self) -> tuple[str, str]:
        return (
            self._a_combo.currentData(),
            self._b_combo.currentData(),
        )


def _match_label(row: _Row) -> str:
    if row.match_type == MATCH_EXACT:
        return T["confirm_match_exact"]
    if row.match_type == MATCH_FUZZY:
        return T["confirm_match_fuzzy"].format(score=row.score)
    return T["confirm_match_manual"]


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line
