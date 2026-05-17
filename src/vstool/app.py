from __future__ import annotations

import sys

# Top-level 导入是必要的：Nuitka 静态分析靠它来识别依赖，
# 之前用 lazy import 导致 Nuitka 打包时漏掉 PySide6 / openpyxl 整个 GUI 链。
from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
