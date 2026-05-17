from __future__ import annotations

from pathlib import Path

from vstool.report import (
    PairOutcome,
    PipelineResult,
    STATUS_FAIL,
    STATUS_OK,
    STATUS_SKIP,
    write_html_summary,
)


def test_summary_contains_all_sections(workdir: Path) -> None:
    result = PipelineResult(
        outcomes=[
            PairOutcome("a.docx", STATUS_OK, workdir / "ok_diff.docx",
                        has_diff=True, notice="已自动接受 2 处修订后再对比"),
            PairOutcome("clean.xlsx", STATUS_OK, workdir / "clean.xlsx",
                        has_diff=False),
            PairOutcome("b.xlsx", STATUS_FAIL, None, "boom"),
            PairOutcome("c.doc", STATUS_SKIP, None, "no com"),
        ],
        only_a=["only_a.docx"],
        only_b=["only_b.docx", "second.xlsx"],
        a_total=7,
        b_total=8,
    )
    path = write_html_summary(workdir, result)
    text = path.read_text(encoding="utf-8")

    assert "总览" in text
    assert "A 侧扫描总数" in text and "B 侧扫描总数" in text
    assert "🔶 有差异的文件" in text
    assert "✅ 无差异的文件" in text
    assert "❌ 失败 / 跳过" in text
    assert "仅 A 有的文件" in text and "仅 B 有的文件" in text

    # 文件名
    assert "a.docx" in text and "clean.xlsx" in text
    assert "b.xlsx" in text and "c.doc" in text
    assert "only_a.docx" in text and "only_b.docx" in text

    # 总览数值（a_total / b_total）
    assert '<div class="v">7</div>' in text
    assert '<div class="v">8</div>' in text

    # 失败原因
    assert "boom" in text and "no com" in text

    # notice 提示出现在有差异段
    assert "已自动接受 2 处修订" in text


def test_pipeline_result_counts_by_has_diff() -> None:
    result = PipelineResult(outcomes=[
        PairOutcome("x", STATUS_OK, has_diff=True),
        PairOutcome("y", STATUS_OK, has_diff=True),
        PairOutcome("z", STATUS_OK, has_diff=False),
        PairOutcome("f", STATUS_FAIL, reason="boom"),
        PairOutcome("s", STATUS_SKIP, reason="skip"),
    ])
    assert result.ok_with_diff == 2
    assert result.ok_no_diff == 1
    assert result.ok_count == 3
    assert result.fail_count == 1
    assert result.skip_count == 1
