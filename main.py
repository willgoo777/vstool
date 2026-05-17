# Nuitka / PyInstaller 的入口。直接拉满 import 让静态分析能看到全部依赖。
from vstool.app import main
from vstool.gui import main_window as _main_window  # noqa: F401
from vstool.gui import worker as _worker            # noqa: F401
from vstool import excel_diff as _excel_diff        # noqa: F401
from vstool import pipeline as _pipeline            # noqa: F401
from vstool import report as _report                # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
