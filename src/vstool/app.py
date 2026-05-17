from __future__ import annotations

import sys


def main() -> int:
    # 延迟导入：脚本 entrypoint 在没 PySide6 的环境下也可以 import vstool 包
    from PySide6.QtWidgets import QApplication

    from .gui.main_window import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
