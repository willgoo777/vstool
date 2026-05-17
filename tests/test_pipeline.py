"""端到端：用 paired_dirs fixture 跑一次完整 pipeline。

macOS 上没有 Word COM，docx 那对会被标 skip；其余 xlsx 对会真正出对比结果。
"""
from __future__ import annotations

from pathlib import Path

from vstool.cancellation import CancellationToken
from vstool.config import OUTPUT_DIFF_SUBDIR, OUTPUT_NODIFF_SUBDIR
from vstool.pairing import MATCH_MANUAL, repair
from vstool.pipeline import run_pipeline, scan_and_pair
from vstool.report import STATUS_OK, STATUS_SKIP
from vstool.scanner import scan


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

    # has_diff 分桶：identical 应在「对比无差异」，values / sub/nested 在「对比有差异」
    assert by_name["identical.xlsx"].has_diff is False
    assert OUTPUT_NODIFF_SUBDIR in str(by_name["identical.xlsx"].output_path)
    for diffed in ("values.xlsx", "sub/nested.xlsx"):
        assert by_name[diffed].has_diff is True, by_name[diffed]
        assert OUTPUT_DIFF_SUBDIR in str(by_name[diffed].output_path)

    # docx 对：mac 上没 Word COM → skip
    assert by_name["letter.docx"].status == STATUS_SKIP

    # 孤儿
    assert "only_a.xlsx" in result.only_a
    assert "only_b.xlsx" in result.only_b

    # a_total / b_total（默认走严格匹配分支：pair 数 + only_* 数）
    # paired_dirs 里 A 共 5 个文件（identical/values/sub/nested/only_a/letter）→ 5
    # B 共 5 个文件（identical/values/sub/nested/only_b/letter）→ 5
    assert result.a_total == 5
    assert result.b_total == 5

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


def test_scan_and_pair_returns_maps(paired_dirs) -> None:
    a, b, _ = paired_dirs
    pr, a_map, b_map = scan_and_pair(a, b)

    # identical / values / sub/nested / letter 是精确同名
    by_key = {p.key: p for p in pr.pairs}
    for k in ("identical.xlsx", "letter.docx", "sub/nested.xlsx", "values.xlsx"):
        assert k in by_key
        assert by_key[k].match_type == "exact"

    # fuzzy 行为：only_a.xlsx 与 only_b.xlsx 名字足够相似（共享 "only_"
    # 前缀和 .xlsx 后缀），会被模糊匹配配上，标 match_type=fuzzy
    assert "only_b.xlsx" in by_key
    assert by_key["only_b.xlsx"].match_type == "fuzzy"
    assert pr.only_a == [] and pr.only_b == []

    # 原始 map 也回来了
    assert "only_a.xlsx" in a_map
    assert "only_b.xlsx" in b_map


def test_pipeline_accepts_prebuilt_pair_result(paired_dirs) -> None:
    """传入用户编辑过的 PairResult：pipeline 跳过 scan/pair，只处理给定的对。"""
    a, b, out = paired_dirs
    a_map = scan(a)
    b_map = scan(b)
    # 只手工保留 values.xlsx 这一对，其它全进 only_*
    manual_pr = repair(a_map, b_map, [("values.xlsx", "values.xlsx")])

    result = run_pipeline(a, b, out, pair_result=manual_pr)

    # 只跑了那一对
    assert len(result.outcomes) == 1
    assert result.outcomes[0].relpath == "values.xlsx"
    assert result.outcomes[0].status == STATUS_OK
    # 其它文件按 only_a / only_b 走 summary
    assert "identical.xlsx" in result.only_a
    assert "identical.xlsx" in result.only_b
    # 配对的 match_type 应是 manual
    assert manual_pr.pairs[0].match_type == MATCH_MANUAL


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
