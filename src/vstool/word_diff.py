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
    WD_NO_PROTECTION,
    WD_SAVE_CHANGES_NO,
)
from .i18n import T


@dataclass
class WordDiffResult:
    output_path: Path
    revision_count: int = 0
    has_changes: bool = False
    notice: str = ""        # 预处理给出的提示（已自动接受修订/解保护/抽取内容）


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

    # ---------- 预处理 ----------

    def _preflight(
        self,
        src_path: Path,
        work_dir: Path,
        protected_workspace_dir: Path,
        rel_for_workspace: str,
    ) -> tuple[Path, str]:
        """对 src_path 做对比前预处理，返回 (实际用于对比的路径, 中文提示)。

        分支：
        1. 受保护 → 尝试 Unprotect()
           - 成功：接着按「有修订则接受」处理
           - 失败：用 FormattedText 复制内容到新 docx，存进受保护工作区
        2. 有未接受修订 → AcceptAllRevisions 后另存到 work_dir
        3. 否则 → 返回原路径，提示为空
        """
        app = self._app
        assert app is not None
        doc = None
        notices: list[str] = []
        try:
            try:
                doc = app.Documents.Open(
                    str(src_path),
                    ReadOnly=False,
                    AddToRecentFiles=False,
                    ConfirmConversions=False,
                    PasswordDocument="__vstool_decoy__",
                )
            except com_error as e:
                raise _classify_open_error(e) from e

            # 1) 处理保护
            protected = False
            try:
                if int(doc.ProtectionType) != WD_NO_PROTECTION:
                    protected = True
            except Exception:
                protected = False

            if protected:
                unprotected = False
                try:
                    doc.Unprotect()
                    unprotected = True
                except Exception:
                    unprotected = False

                if not unprotected:
                    # 抽取内容到新 docx 存进工作区
                    cleaned_path = _protected_copy_path(
                        protected_workspace_dir, rel_for_workspace, src_path)
                    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        new_doc = app.Documents.Add()
                        try:
                            new_doc.Content.FormattedText = doc.Content.FormattedText
                            new_doc.SaveAs2(
                                str(cleaned_path),
                                FileFormat=WD_FORMAT_DOCUMENT_DEFAULT,
                            )
                        finally:
                            try:
                                new_doc.Close(SaveChanges=WD_SAVE_CHANGES_NO)
                            except Exception:
                                pass
                    except com_error as e:
                        raise WordDiffError(
                            T["reason_word_preflight_failed"].format(
                                stage="复制受保护内容", msg=str(e)),
                            e,
                        ) from e
                    notices.append(
                        T["reason_word_protected_copied"].format(path=rel_for_workspace))
                    return cleaned_path, "；".join(notices)

                notices.append(T["reason_word_unprotected"])

            # 2) 处理修订
            try:
                rev_count = int(doc.Revisions.Count)
            except Exception:
                rev_count = 0

            if rev_count > 0:
                try:
                    doc.AcceptAllRevisions()
                except com_error as e:
                    raise WordDiffError(
                        T["reason_word_preflight_failed"].format(
                            stage="接受修订", msg=str(e)),
                        e,
                    ) from e
                cleaned_path = _accepted_copy_path(work_dir, src_path)
                cleaned_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    doc.SaveAs2(
                        str(cleaned_path),
                        FileFormat=WD_FORMAT_DOCUMENT_DEFAULT,
                    )
                except com_error as e:
                    raise WordDiffError(
                        T["reason_word_preflight_failed"].format(
                            stage="保存接受修订后的副本", msg=str(e)),
                        e,
                    ) from e
                notices.append(
                    T["reason_word_revisions_accepted"].format(n=rev_count))
                return cleaned_path, "；".join(notices)

            # 3) 无须处理；但如果之前解了保护，需要把解保护后的版本另存
            if notices:
                cleaned_path = _accepted_copy_path(work_dir, src_path)
                cleaned_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    doc.SaveAs2(
                        str(cleaned_path),
                        FileFormat=WD_FORMAT_DOCUMENT_DEFAULT,
                    )
                except com_error as e:
                    raise WordDiffError(
                        T["reason_word_preflight_failed"].format(
                            stage="保存解保护后的副本", msg=str(e)),
                        e,
                    ) from e
                return cleaned_path, "；".join(notices)

            return src_path, ""
        finally:
            if doc is not None:
                try:
                    doc.Close(SaveChanges=WD_SAVE_CHANGES_NO)
                except Exception:
                    pass

    # ---------- 对比 ----------

    def compare(
        self,
        a_path: Path,
        b_path: Path,
        out_path: Path,
        *,
        work_dir: Path,
        protected_workspace_dir: Path,
        rel_path: str,
    ) -> WordDiffResult:
        if self._app is None:
            raise RuntimeError("WordDiffer 未通过 with 语句初始化")
        app = self._app
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 预处理两侧
        a_use, hint_a = self._preflight(
            a_path, work_dir / "a", protected_workspace_dir, f"A/{rel_path}")
        b_use, hint_b = self._preflight(
            b_path, work_dir / "b", protected_workspace_dir, f"B/{rel_path}")
        notice = "；".join(h for h in (hint_a, hint_b) if h)

        doc_a = doc_b = doc_diff = None
        try:
            try:
                doc_a = app.Documents.Open(
                    str(a_use),
                    ReadOnly=True,
                    AddToRecentFiles=False,
                    ConfirmConversions=False,
                    PasswordDocument="__vstool_decoy__",
                )
                doc_b = app.Documents.Open(
                    str(b_use),
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
                raise _classify_compare_error(e) from e

            try:
                rev_count = int(doc_diff.Revisions.Count)
            except Exception:
                rev_count = 0

            try:
                doc_diff.SaveAs2(str(out_path), FileFormat=WD_FORMAT_DOCUMENT_DEFAULT)
            except com_error as e:
                raise WordDiffError(f"保存对比结果失败：{e}", e) from e

            return WordDiffResult(
                output_path=out_path,
                revision_count=rev_count,
                has_changes=rev_count > 0,
                notice=notice,
            )
        finally:
            for d in (doc_diff, doc_a, doc_b):
                if d is None:
                    continue
                try:
                    d.Close(SaveChanges=WD_SAVE_CHANGES_NO)
                except Exception:
                    pass


# ---------- 辅助 ----------

def _accepted_copy_path(work_dir: Path, src_path: Path) -> Path:
    """work_dir/<src.stem>__cleaned.docx；用 hash 避免重名碰撞。"""
    import hashlib
    digest = hashlib.md5(str(src_path).encode("utf-8")).hexdigest()[:8]
    return work_dir / f"{src_path.stem}__{digest}__cleaned.docx"


def _protected_copy_path(workspace_root: Path, rel: str, src_path: Path) -> Path:
    rel_p = Path(rel)
    return workspace_root / rel_p.parent / f"{src_path.stem}__cleaned.docx"


# ---------- 错误分类 ----------

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


def _classify_compare_error(e: BaseException) -> WordDiffError:
    raw = str(e)
    msg = raw.lower()
    # HRESULT -2147352567 = 0x80020009 = 「发生意外。」
    # 典型触发：含未接受修订（即便我们已 AcceptAll，部分嵌入对象的痕迹仍会触发）；
    # 文档结构异常；插件冲突。
    if "-2147352567" in raw or "发生意外" in raw or "exception occurred" in msg:
        return WordDiffError(
            T["reason_word_compare_unexpected"].format(raw=raw), e)
    return WordDiffError(f"CompareDocuments 失败：{e}", e)
