""".xls → .xlsx 转换器（Excel COM）。仅 Windows + 已装 MS Excel 可用。

整批共用一个 Excel.Application 实例，转换文件落到调用方提供的临时目录里。
"""
from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any

from .com_utils import com_error, dispatch, require_com
from .config import XL_OPENXML_WORKBOOK


class ExcelConvertError(Exception):
    def __init__(self, reason: str, raw: BaseException | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.raw = raw


class ExcelConverter:
    def __init__(self) -> None:
        require_com("Excel.Application")
        self._app: Any | None = None

    def __enter__(self) -> "ExcelConverter":
        app = dispatch("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        try:
            app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        except Exception:
            pass
        self._app = app
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._app is None:
            return
        try:
            self._app.Quit()
        except Exception:
            pass
        finally:
            self._app = None

    def convert_to_xlsx(self, src: Path, dst: Path) -> Path:
        if self._app is None:
            raise RuntimeError("ExcelConverter 未通过 with 语句初始化")
        wb = None
        try:
            try:
                wb = self._app.Workbooks.Open(
                    str(src),
                    ReadOnly=True,
                    UpdateLinks=0,
                    Password="__vstool_decoy__",
                )
            except com_error as e:
                raise _classify_open_error(e) from e
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                wb.SaveAs(str(dst), FileFormat=XL_OPENXML_WORKBOOK)
            except com_error as e:
                raise ExcelConvertError(f"SaveAs xlsx 失败：{e}", e) from e
            return dst
        finally:
            if wb is not None:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass


def _classify_open_error(e: BaseException) -> ExcelConvertError:
    msg = str(e).lower()
    if "password" in msg or "密码" in msg:
        return ExcelConvertError("文件受密码保护", e)
    if "in use" in msg or "占用" in msg or "lock" in msg:
        return ExcelConvertError("文件被其他程序占用", e)
    return ExcelConvertError(f"打开 .xls 失败：{e}", e)
