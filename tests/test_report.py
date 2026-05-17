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
            PairOutcome("a.docx", STATUS_OK, workdir / "out.docx"),
            PairOutcome("b.xlsx", STATUS_FAIL, None, "boom"),
            PairOutcome("c.doc", STATUS_SKIP, None, "no com"),
        ],
        only_a=["only_a.docx"],
        only_b=["only_b.docx", "second.xlsx"],
    )
    path = write_html_summary(workdir, result)
    text = path.read_text(encoding="utf-8")

    assert "总览" in text
    assert "仅 A 有的文件" in text
    assert "仅 B 有的文件" in text
    assert "a.docx" in text and "b.xlsx" in text and "c.doc" in text
    assert "only_a.docx" in text and "only_b.docx" in text
    assert "boom" in text
    # 数量统计
    assert "<div class=\"v\">3</div>" in text  # total
    assert ">1</div>" in text                  # ok / fail / skip 各 1
