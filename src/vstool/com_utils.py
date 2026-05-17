from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any, Iterator

# 只有 Windows 上才有 win32com / pythoncom。macOS 下保持 None 以便 import 通过、
# 真正实例化 WordDiffer / ExcelConverter 时再报清晰错误。
try:
    import win32com.client as _win32com_client  # type: ignore[import-not-found]
    import pythoncom as _pythoncom  # type: ignore[import-not-found]
    import pywintypes as _pywintypes  # type: ignore[import-not-found]

    HAS_COM: bool = True
    com_error: type[BaseException] = _pywintypes.com_error
except ImportError:  # 非 Windows 或未装 pywin32
    _win32com_client = None
    _pythoncom = None
    _pywintypes = None
    HAS_COM = False

    class _FakeComError(Exception):
        pass

    com_error = _FakeComError


def require_com(component: str) -> None:
    """实例化 COM 包装类时调用；不可用就抛出清晰错误。"""
    if not HAS_COM:
        raise RuntimeError(
            f"需要 Windows + Microsoft Office 才能使用 {component}。"
            f"当前平台 {sys.platform} 未检测到 pywin32。"
        )


def dispatch(prog_id: str) -> Any:
    """晚期绑定 Dispatch。绝不调用 EnsureDispatch，避免 PyInstaller 冻结后写 gen_py。"""
    require_com(prog_id)
    return _win32com_client.Dispatch(prog_id)


@contextmanager
def com_initialized() -> Iterator[None]:
    """在非主线程（如 QThread.run）使用 COM 前必须调用 CoInitialize。"""
    if not HAS_COM:
        yield
        return
    _pythoncom.CoInitialize()
    try:
        yield
    finally:
        _pythoncom.CoUninitialize()
