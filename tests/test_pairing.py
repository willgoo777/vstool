from __future__ import annotations

from pathlib import Path

from vstool.pairing import pair
from vstool.scanner import ScannedFile


def _sf(rel: str) -> ScannedFile:
    return ScannedFile(relpath=rel, abspath=Path(f"/fake/{rel}"))


def test_pair_splits_common_and_orphans() -> None:
    a = {"x.docx": _sf("x.docx"), "y.xlsx": _sf("y.xlsx")}
    b = {"x.docx": _sf("x.docx"), "z.docx": _sf("z.docx")}
    r = pair(a, b)
    assert [p.key for p in r.pairs] == ["x.docx"]
    assert [f.relpath for f in r.only_a] == ["y.xlsx"]
    assert [f.relpath for f in r.only_b] == ["z.docx"]


def test_pair_uses_b_relpath_for_display() -> None:
    a = {"x.docx": ScannedFile("X.DOCX", Path("/a/X.DOCX"))}
    b = {"x.docx": ScannedFile("x.docx", Path("/b/x.docx"))}
    r = pair(a, b)
    assert r.pairs[0].relpath == "x.docx"
    assert r.pairs[0].ext == ".docx"
