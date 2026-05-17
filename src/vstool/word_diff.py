"""Word 文件对比：用 MS Word COM 的 Application.CompareDocuments 生成原生修订文档。

仅 Windows + 已装 MS Word 可用。WordDiffer 作为上下文管理器一次起一个 Word.Application
进程，整批复用，最后关掉。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any

from .com_utils import com_error, dispatch, require_com
from .config import (
    WD_ALERTS_NONE,
    WD_AUTOMATION_SECURITY_FORCE_DISABLE,
    WD_COMPARE_DESTINATION_NEW,
    WD_FORMAT_DOCUMENT_DEFAULT,
    WD_SAVE_CHANGES_NO,
)


@dataclass
class WordDiffResult:
    output_path: Path


class WordDiffError(Exception):
    """打开/对比/保存阶段的 COM 错误。"""

    def __init__(self, reason: str, raw: BaseException | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.raw = raw


class WordDiffer:
    def __init__(self) -> None:
        require_com("Word.Application")
        self._app: Any | None = None

    def __enter__(self) -> "WordDiffer":
        app = dispatch("Word.Application")
        app.Visible = False
        app.DisplayAlerts = WD_ALERTS_NONE
        # 屏蔽宏自动执行
        try:
            app.AutomationSecurity = WD_AUTOMATION_SECURITY_FORCE_DISABLE
        except Exception:
            # 老版本 Word 可能没有此属性，忽略
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
            self._app.Quit(SaveChanges=WD_SAVE_CHANGES_NO)
        except Exception:
            pass
        finally:
            self._app = None

    def compare(self, a_path: Path, b_path: Path, out_path: Path) -> WordDiffResult:
        if self._app is None:
            raise RuntimeError("WordDiffer 未通过 with 语句初始化")
        app = self._app
        out_path.parent.mkdir(parents=True, exist_ok=True)

        doc_a = doc_b = doc_diff = None
        try:
            try:
                # 假密码：受密码保护的文件直接抛错而不是弹窗等待
                doc_a = app.Documents.Open(
                    str(a_path),
                    ReadOnly=True,
                    AddToRecentFiles=False,
                    ConfirmConversions=False,
                    PasswordDocument="__vstool_decoy__",
                )
                doc_b = app.Documents.Open(
                    str(b_path),
                    ReadOnly=True,
                    AddToRecentFiles=False,
                    ConfirmConversions=False,
                    PasswordDocument="__vstool_decoy__",
                )
            except com_error as e:
                raise _classify_open_error(e) from e

            try:
                doc_diff = app.CompareDocuments(
                    OriginalDocument=doc_a,
                    RevisedDocument=doc_b,
                    Destination=WD_COMPARE_DESTINATION_NEW,
                    Granularity=1,
                    CompareFormatting=True,
                    CompareCaseChanges=True,
                    CompareWhitespace=False,
                    CompareTables=True,
                    CompareHeaders=True,
                    CompareFootnotes=True,
                    CompareTextboxes=True,
                    CompareFields=True,
                    CompareComments=True,
                    CompareMoves=True,
                )
            except com_error as e:
                raise WordDiffError(f"CompareDocuments 失败：{e}", e) from e

            try:
                doc_diff.SaveAs2(str(out_path), FileFormat=WD_FORMAT_DOCUMENT_DEFAULT)
            except com_error as e:
                raise WordDiffError(f"保存对比结果失败：{e}", e) from e

            return WordDiffResult(output_path=out_path)
        finally:
            for d in (doc_diff, doc_a, doc_b):
                if d is None:
                    continue
                try:
                    d.Close(SaveChanges=WD_SAVE_CHANGES_NO)
                except Exception:
                    pass


def _classify_open_error(e: BaseException) -> WordDiffError:
    msg = str(e).lower()
    # Word COM 的错误信息常含中英文混合，做宽松匹配
    if "password" in msg or "密码" in msg:
        return WordDiffError("文件受密码保护", e)
    if "in use" in msg or "占用" in msg or "lock" in msg:
        return WordDiffError("文件被其他程序占用", e)
    if "could not be found" in msg or "not exist" in msg or "找不到" in msg:
        return WordDiffError("文件不存在或无法打开", e)
    return WordDiffError(f"打开文档失败：{e}", e)
