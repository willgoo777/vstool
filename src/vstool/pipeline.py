"""核心编排：扫描 → 配对 → 分发 → 汇总。

run_pipeline 同时被 GUI worker 和测试调用，通过 on_event 回调把过程事件抛出去，
不直接耦合 Qt。
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import com_utils
from .cancellation import CancellationToken, OperationCancelled
from .config import (
    OUTPUT_EXCEL_SUBDIR,
    OUTPUT_WORD_SUBDIR,
    SUPPORTED_EXCEL_EXTS,
    SUPPORTED_WORD_EXTS,
)
from .excel_diff import diff_workbooks
from .i18n import T
from .pairing import FilePair, PairResult, fuzzy_pair, pair
from .report import (
    PairOutcome,
    PipelineResult,
    STATUS_FAIL,
    STATUS_OK,
    STATUS_SKIP,
    write_html_summary,
)
from .scanner import ScannedFile, scan


# ---------- 事件 ----------

@dataclass
class Event:
    kind: str           # "log" / "progress" / "pair_done"
    message: str = ""
    current: int = 0
    total: int = 0


OnEvent = Callable[[Event], None]


def _noop(_: Event) -> None:
    pass


# ---------- 仅扫描 + 配对 ----------

def scan_and_pair(
    a_dir: Path,
    b_dir: Path,
    on_event: OnEvent = _noop,
) -> tuple[PairResult, dict[str, ScannedFile], dict[str, ScannedFile]]:
    """扫描 A、B 并跑模糊配对，返回 (PairResult, a_map, b_map)。

    GUI 在主线程同步调用这一步，再把 PairResult 喂给确认对话框，
    用户编辑后由 run_pipeline 拿编辑过的版本继续跑耗时任务。
    """
    a_dir = a_dir.resolve()
    b_dir = b_dir.resolve()

    on_event(Event("log", T["status_scanning"]))
    on_event(Event("log", T["log_scan_a"].format(root=a_dir)))
    a_map = scan(a_dir)
    on_event(Event("log", T["log_scan_b"].format(root=b_dir)))
    b_map = scan(b_dir)

    on_event(Event("log", T["status_pairing"]))
    pr = fuzzy_pair(a_map, b_map)
    on_event(Event("log", T["log_found"].format(
        a=len(a_map), b=len(b_map),
        p=len(pr.pairs), oa=len(pr.only_a), ob=len(pr.only_b),
    )))
    return pr, a_map, b_map


# ---------- 主入口 ----------

def run_pipeline(
    a_dir: Path,
    b_dir: Path,
    out_dir: Path,
    pair_result: PairResult | None = None,
    token: CancellationToken | None = None,
    on_event: OnEvent = _noop,
) -> PipelineResult:
    token = token or CancellationToken()
    a_dir = a_dir.resolve()
    b_dir = b_dir.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = PipelineResult()

    if pair_result is None:
        # 编程接口默认走严格同名匹配；GUI 想要模糊匹配请先调 scan_and_pair。
        on_event(Event("log", T["status_scanning"]))
        on_event(Event("log", T["log_scan_a"].format(root=a_dir)))
        a_map = scan(a_dir)
        on_event(Event("log", T["log_scan_b"].format(root=b_dir)))
        b_map = scan(b_dir)
        on_event(Event("log", T["status_pairing"]))
        pr = pair(a_map, b_map)
        on_event(Event("log", T["log_found"].format(
            a=len(a_map), b=len(b_map),
            p=len(pr.pairs), oa=len(pr.only_a), ob=len(pr.only_b),
        )))
    else:
        pr = pair_result
    result.only_a = [f.relpath for f in pr.only_a]
    result.only_b = [f.relpath for f in pr.only_b]

    total = len(pr.pairs)
    on_event(Event("progress", current=0, total=total))

    # 一次性起 WordDiffer / ExcelConverter（如果有 COM 且有相应任务）
    needs_word = any(p.ext in SUPPORTED_WORD_EXTS for p in pr.pairs)
    needs_xls = any(p.ext == ".xls" for p in pr.pairs)

    word_differ_cm = _maybe_word_differ(needs_word, result, pr.pairs, on_event)
    excel_converter_cm = _maybe_excel_converter(needs_xls, on_event)

    try:
        with tempfile.TemporaryDirectory(prefix="vstool_xls_") as tmpdir:
            tmp = Path(tmpdir)
            with word_differ_cm as word_differ, excel_converter_cm as xls_conv:
                for i, p in enumerate(pr.pairs, 1):
                    try:
                        token.raise_if_cancelled()
                    except OperationCancelled:
                        result.cancelled = True
                        on_event(Event("log", T["status_cancelled"].format(
                            done=i - 1, total=total)))
                        break

                    on_event(Event("log", T["status_pair_progress"].format(
                        i=i, n=total, name=p.relpath)))
                    outcome = _process_pair(p, out_dir, tmp, word_differ, xls_conv)
                    result.outcomes.append(outcome)
                    _emit_pair_log(outcome, on_event)
                    on_event(Event("progress", current=i, total=total))
    finally:
        summary_path = write_html_summary(out_dir, result)
        result.summary_path = summary_path
        on_event(Event("log", T["log_summary_written"].format(path=summary_path)))

    if result.cancelled:
        on_event(Event("log", T["status_cancelled"].format(
            done=len(result.outcomes), total=total)))
    else:
        on_event(Event("log", T["status_done"].format(
            n=result.total, ok=result.ok_count,
            fail=result.fail_count, skip=result.skip_count)))

    return result


# ---------- 单对处理 ----------

def _process_pair(
    p: FilePair,
    out_root: Path,
    tmpdir: Path,
    word_differ,
    xls_conv,
) -> PairOutcome:
    try:
        if p.ext in SUPPORTED_WORD_EXTS:
            return _process_word(p, out_root, word_differ)
        if p.ext in SUPPORTED_EXCEL_EXTS:
            return _process_excel(p, out_root, tmpdir, xls_conv)
        return PairOutcome(p.relpath, STATUS_SKIP, None, T["reason_unsupported_ext"])
    except Exception as e:  # 包兜底，单对失败不应崩 pipeline
        msg = str(e) or e.__class__.__name__
        return PairOutcome(p.relpath, STATUS_FAIL, None,
                           T["reason_unknown"].format(msg=msg))


def _word_out_path(p: FilePair, out_root: Path) -> Path:
    rel = Path(p.relpath)
    return out_root / OUTPUT_WORD_SUBDIR / rel.parent / f"{rel.stem}_diff.docx"


def _excel_out_path(p: FilePair, out_root: Path) -> Path:
    rel = Path(p.relpath)
    return out_root / OUTPUT_EXCEL_SUBDIR / rel.parent / f"{rel.stem}_diff.xlsx"


def _process_word(p: FilePair, out_root: Path, word_differ) -> PairOutcome:
    if word_differ is None:
        return PairOutcome(p.relpath, STATUS_SKIP, None, T["reason_word_no_com"])
    out = _word_out_path(p, out_root)
    try:
        word_differ.compare(p.a_path, p.b_path, out)
        return PairOutcome(p.relpath, STATUS_OK, out, "")
    except Exception as e:
        reason = getattr(e, "reason", None) or str(e)
        return PairOutcome(p.relpath, STATUS_FAIL, None, reason)


def _process_excel(p: FilePair, out_root: Path, tmpdir: Path, xls_conv) -> PairOutcome:
    a_path = p.a_path
    b_path = p.b_path

    # 旧格式先转 xlsx
    if p.ext == ".xls":
        if xls_conv is None:
            return PairOutcome(p.relpath, STATUS_SKIP, None, T["reason_xls_no_com"])
        try:
            a_path = xls_conv.convert_to_xlsx(
                p.a_path, tmpdir / f"a__{_safe_name(p.relpath)}.xlsx")
            b_path = xls_conv.convert_to_xlsx(
                p.b_path, tmpdir / f"b__{_safe_name(p.relpath)}.xlsx")
        except Exception as e:
            reason = getattr(e, "reason", None) or str(e)
            return PairOutcome(p.relpath, STATUS_FAIL, None, reason)

    out = _excel_out_path(p, out_root)
    try:
        diff_workbooks(a_path, b_path, out)
        return PairOutcome(p.relpath, STATUS_OK, out, "")
    except Exception as e:
        return PairOutcome(p.relpath, STATUS_FAIL, None, str(e))


def _safe_name(relpath: str) -> str:
    return relpath.replace("/", "__").replace("\\", "__")


def _emit_pair_log(o: PairOutcome, on_event: OnEvent) -> None:
    if o.status == STATUS_OK:
        on_event(Event("log", T["log_pair_ok"].format(
            name=o.relpath, out=o.output_path)))
    elif o.status == STATUS_SKIP:
        on_event(Event("log", T["log_pair_skip"].format(
            name=o.relpath, reason=o.reason)))
    else:
        on_event(Event("log", T["log_pair_fail"].format(
            name=o.relpath, reason=o.reason)))


# ---------- 可选 COM 资源的上下文管理器 ----------

class _NullCM:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


class _SafeCM:
    """包一层：__enter__ 阶段如果底层抛错（典型场景：装了 pywin32 但没装 Word/
    Excel，Dispatch 报 Invalid class string），把异常吞掉、回调汇报、yield None，
    后续 pipeline 把对应 pair 标记为 skip。"""

    def __init__(self, factory, on_error):
        self._factory = factory
        self._on_error = on_error
        self._cm = None

    def __enter__(self):
        try:
            self._cm = self._factory()
            return self._cm.__enter__()
        except Exception as e:
            self._on_error(e)
            self._cm = None
            return None

    def __exit__(self, *args):
        if self._cm is not None:
            try:
                return self._cm.__exit__(*args)
            except Exception:
                return False
        return False


def _maybe_word_differ(needed: bool, result: PipelineResult,
                       pairs, on_event: OnEvent):
    if not needed:
        return _NullCM()
    if not com_utils.HAS_COM:
        on_event(Event("log", T["reason_word_no_com"]))
        return _NullCM()
    from .word_diff import WordDiffer  # 局部导入，macOS 下也能 import 包

    def _on_err(e):
        on_event(Event("log", T["reason_word_no_app"].format(msg=e)))

    return _SafeCM(WordDiffer, _on_err)


def _maybe_excel_converter(needed: bool, on_event: OnEvent = _noop):
    if not needed:
        return _NullCM()
    if not com_utils.HAS_COM:
        return _NullCM()
    from .excel_legacy import ExcelConverter

    def _on_err(e):
        on_event(Event("log", T["reason_excel_no_app"].format(msg=e)))

    return _SafeCM(ExcelConverter, _on_err)


__all__ = [
    "Event", "OnEvent", "run_pipeline", "scan_and_pair",
    "PipelineResult", "PairOutcome",
]
