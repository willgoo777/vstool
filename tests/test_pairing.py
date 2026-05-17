from __future__ import annotations

from pathlib import Path

from vstool.pairing import (
    MATCH_EXACT,
    MATCH_FUZZY,
    MATCH_MANUAL,
    fuzzy_pair,
    pair,
    repair,
)
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


def test_pair_default_match_type_is_exact() -> None:
    a = {"x.docx": _sf("x.docx")}
    b = {"x.docx": _sf("x.docx")}
    r = pair(a, b)
    assert r.pairs[0].match_type == MATCH_EXACT
    assert r.pairs[0].score == 1.0


# ---------- fuzzy_pair ----------

def test_fuzzy_pair_matches_version_suffix() -> None:
    a = {"report_v1.docx": _sf("report_v1.docx")}
    b = {"report_v2.docx": _sf("report_v2.docx")}
    r = fuzzy_pair(a, b)
    assert len(r.pairs) == 1
    p = r.pairs[0]
    assert p.match_type == MATCH_FUZZY
    assert p.a_path == Path("/fake/report_v1.docx")
    assert p.b_path == Path("/fake/report_v2.docx")
    assert p.relpath == "report_v2.docx"  # 显示用 B 的
    assert 0.6 <= p.score < 1.0
    assert r.only_a == [] and r.only_b == []


def test_fuzzy_pair_respects_threshold() -> None:
    # 完全不相似的两个名字不应配上
    a = {"alpha.docx": _sf("alpha.docx")}
    b = {"zztop_zztop_zztop.docx": _sf("zztop_zztop_zztop.docx")}
    r = fuzzy_pair(a, b, threshold=0.6)
    assert r.pairs == []
    assert [f.relpath for f in r.only_a] == ["alpha.docx"]
    assert [f.relpath for f in r.only_b] == ["zztop_zztop_zztop.docx"]


def test_fuzzy_pair_cross_dir_same_ext() -> None:
    # 跨目录但同扩展名可以配
    a = {"old/report_v1.docx": _sf("old/report_v1.docx")}
    b = {"new/report_v2.docx": _sf("new/report_v2.docx")}
    r = fuzzy_pair(a, b)
    assert len(r.pairs) == 1
    assert r.pairs[0].match_type == MATCH_FUZZY

    # 但跨扩展名不会配
    a2 = {"report_v1.docx": _sf("report_v1.docx")}
    b2 = {"report_v1.xlsx": _sf("report_v1.xlsx")}
    r2 = fuzzy_pair(a2, b2)
    assert r2.pairs == []
    assert len(r2.only_a) == 1 and len(r2.only_b) == 1


def test_fuzzy_pair_greedy_no_collision() -> None:
    # 两个 A 都跟同一个 B 相似，B 只能被配一次
    a = {
        "report_v1.docx": _sf("report_v1.docx"),
        "report_v3.docx": _sf("report_v3.docx"),
    }
    b = {"report_v2.docx": _sf("report_v2.docx")}
    r = fuzzy_pair(a, b)
    assert len(r.pairs) == 1
    assert len(r.only_a) == 1
    assert r.only_b == []


def test_fuzzy_pair_keeps_exact_pairs_first() -> None:
    # 严格同名优先，剩余项才走模糊
    a = {
        "x.docx": _sf("x.docx"),
        "report_v1.docx": _sf("report_v1.docx"),
    }
    b = {
        "x.docx": _sf("x.docx"),
        "report_v2.docx": _sf("report_v2.docx"),
    }
    r = fuzzy_pair(a, b)
    by_key = {p.key: p for p in r.pairs}
    assert by_key["x.docx"].match_type == MATCH_EXACT
    assert by_key["report_v2.docx"].match_type == MATCH_FUZZY


# ---------- repair ----------

def test_repair_builds_manual_pairs() -> None:
    a = {"foo.docx": _sf("foo.docx"), "bar.xlsx": _sf("bar.xlsx")}
    b = {"baz.docx": _sf("baz.docx"), "qux.xlsx": _sf("qux.xlsx")}
    r = repair(a, b, [("foo.docx", "baz.docx")])
    assert len(r.pairs) == 1
    assert r.pairs[0].match_type == MATCH_MANUAL
    assert r.pairs[0].key == "baz.docx"
    assert [f.relpath for f in r.only_a] == ["bar.xlsx"]
    assert [f.relpath for f in r.only_b] == ["qux.xlsx"]


def test_repair_skips_unknown_keys() -> None:
    a = {"foo.docx": _sf("foo.docx")}
    b = {"bar.docx": _sf("bar.docx")}
    r = repair(a, b, [("nope.docx", "bar.docx"), ("foo.docx", "nope.docx")])
    assert r.pairs == []
    assert [f.relpath for f in r.only_a] == ["foo.docx"]
    assert [f.relpath for f in r.only_b] == ["bar.docx"]
