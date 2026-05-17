"""端到端：用 paired_dirs fixture 跑一次完整 pipeline。

macOS 上没有 Word COM，docx 那对会被标 skip；其余 xlsx 对会真正出对比结果。
"""
from __future__ import annotations

from pathlib import Path

from vstool.cancellation import CancellationToken
from vstool.pipeline import run_pipeline
from vstool.report import STATUS_OK, STATUS_SKIP


def test_pipeline_end_to_end_on_macos(paired_dirs) -> None:
    a, b, out = paired_dirs
    result = run_pipeline(a, b, out, token=CancellationToken())

    by_name = {o.relpath: o for o in result.outcomes}

    # xlsx 对：identical / values / sub/nested 都应成功
    for name in ("identical.xlsx", "values.xlsx", "sub/nested.xlsx"):
        assert name in by_name, by_name
        assert by_name[name].status == STATUS_OK, by_name[name]
        assert by_name[name].output_path is not None
        assert by_name[name].output_path.exists()

    # docx 对：mac 上没 Word COM → skip
    assert by_name["letter.docx"].status == STATUS_SKIP

    # 孤儿
    assert "only_a.xlsx" in result.only_a
    assert "only_b.xlsx" in result.only_b

    # summary.html 存在
    assert result.summary_path is not None and result.summary_path.exists()


def test_pipeline_degrades_when_office_missing(paired_dirs, monkeypatch) -> None:
    """模拟 Windows 上装了 pywin32 但没装 Word / Excel：
    HAS_COM=True 但 Dispatch 抛 com_error。应优雅降级把 word 对标 skip，
    不影响 xlsx 对的正常完成。"""
    a, b, out = paired_dirs

    import vstool.com_utils as cu
    import vstool.pipeline as pl
    import vstool.word_diff as wd
    import vstool.excel_legacy as el

    class FakeComError(Exception):
        pass

    def boom(_prog_id):
        raise FakeComError("Invalid class string")

    monkeypatch.setattr(cu, "HAS_COM", True)
    monkeypatch.setattr(cu, "com_error", FakeComError)
    monkeypatch.setattr(wd, "dispatch", boom)
    monkeypatch.setattr(el, "dispatch", boom)
    monkeypatch.setattr(wd, "require_com", lambda *a, **k: None)
    monkeypatch.setattr(el, "require_com", lambda *a, **k: None)
    monkeypatch.setattr(pl.com_utils, "HAS_COM", True)

    result = pl.run_pipeline(a, b, out)

    by_name = {o.relpath: o for o in result.outcomes}
    # Word 对：降级为 skip 而不是炸
    assert by_name["letter.docx"].status == STATUS_SKIP
    # xlsx 对仍正常完成
    assert by_name["values.xlsx"].status == STATUS_OK


def test_pipeline_cancel_between_pairs(paired_dirs) -> None:
    """触发取消的最简方式：取消令牌一进入就置位。"""
    a, b, out = paired_dirs
    token = CancellationToken()
    token.cancel()
    result = run_pipeline(a, b, out, token=token)
    assert result.cancelled is True
    assert len(result.outcomes) == 0
    # 即使取消，summary 也要写
    assert result.summary_path is not None and result.summary_path.exists()
