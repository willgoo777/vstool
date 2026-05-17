from __future__ import annotations

from pathlib import Path

from vstool.scanner import scan


def test_scan_finds_supported_files_and_excludes_temp(workdir: Path) -> None:
    (workdir / "a.docx").write_text("dummy")
    (workdir / "b.xlsx").write_text("dummy")
    (workdir / "c.txt").write_text("dummy")          # 不在白名单
    (workdir / "~$lock.docx").write_text("dummy")    # Office lock
    (workdir / ".hidden.docx").write_text("dummy")   # 隐藏文件
    sub = workdir / "sub"
    sub.mkdir()
    (sub / "d.xlsx").write_text("dummy")

    result = scan(workdir)
    keys = set(result)
    assert keys == {"a.docx", "b.xlsx", "sub/d.xlsx"}


def test_scan_is_case_insensitive_for_keys(workdir: Path) -> None:
    (workdir / "Report.DOCX").write_text("dummy")
    result = scan(workdir)
    assert "report.docx" in result
    # 但 relpath 保留原始大小写
    assert result["report.docx"].relpath == "Report.DOCX"


def test_scan_raises_on_missing_dir(workdir: Path) -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        scan(workdir / "nope")
