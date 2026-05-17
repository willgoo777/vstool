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
