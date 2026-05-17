from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath

from .scanner import ScannedFile

MATCH_EXACT = "exact"
MATCH_FUZZY = "fuzzy"
MATCH_MANUAL = "manual"

DEFAULT_FUZZY_THRESHOLD = 0.6


@dataclass(frozen=True)
class FilePair:
    key: str           # 小写归一化后的相对路径（取 B 的，保证唯一性）
    relpath: str       # 显示用，取 B 的原始大小写（输出镜像 B）
    ext: str           # 小写扩展名，含点
    a_path: Path
    b_path: Path
    match_type: str = MATCH_EXACT     # "exact" | "fuzzy" | "manual"
    score: float = 1.0                 # 相似度 0-1


@dataclass
class PairResult:
    pairs: list[FilePair] = field(default_factory=list)
    only_a: list[ScannedFile] = field(default_factory=list)
    only_b: list[ScannedFile] = field(default_factory=list)


def _make_pair(
    a: ScannedFile,
    b: ScannedFile,
    match_type: str,
    score: float,
) -> FilePair:
    return FilePair(
        key=b.relpath.lower(),
        relpath=b.relpath,
        ext=Path(b.relpath).suffix.lower(),
        a_path=a.abspath,
        b_path=b.abspath,
        match_type=match_type,
        score=score,
    )


def pair(
    a_map: dict[str, ScannedFile],
    b_map: dict[str, ScannedFile],
) -> PairResult:
    """按归一化 key 严格配对。输出按 relpath 排序，便于稳定显示和测试。"""
    common = sorted(set(a_map) & set(b_map))
    only_a_keys = sorted(set(a_map) - set(b_map))
    only_b_keys = sorted(set(b_map) - set(a_map))

    pairs = [_make_pair(a_map[k], b_map[k], MATCH_EXACT, 1.0) for k in common]
    return PairResult(
        pairs=pairs,
        only_a=[a_map[k] for k in only_a_keys],
        only_b=[b_map[k] for k in only_b_keys],
    )


def fuzzy_pair(
    a_map: dict[str, ScannedFile],
    b_map: dict[str, ScannedFile],
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> PairResult:
    """先严格配对，剩余项按扩展名分桶后用 SequenceMatcher 贪心模糊配对。

    跨目录可配（按用户设定）；同扩展名才比相似度；ratio < threshold 不配。
    """
    base = pair(a_map, b_map)

    rem_a = {sf.relpath.lower(): sf for sf in base.only_a}
    rem_b = {sf.relpath.lower(): sf for sf in base.only_b}

    buckets_a: dict[str, list[str]] = defaultdict(list)
    buckets_b: dict[str, list[str]] = defaultdict(list)
    for k, sf in rem_a.items():
        buckets_a[Path(sf.relpath).suffix.lower()].append(k)
    for k, sf in rem_b.items():
        buckets_b[Path(sf.relpath).suffix.lower()].append(k)

    fuzzy_pairs: list[FilePair] = []
    used_a: set[str] = set()
    used_b: set[str] = set()

    for ext, a_keys in buckets_a.items():
        b_keys = buckets_b.get(ext)
        if not b_keys:
            continue
        candidates: list[tuple[float, str, str]] = []
        for ak in a_keys:
            a_stem = _stem_no_ext(rem_a[ak].relpath)
            for bk in b_keys:
                b_stem = _stem_no_ext(rem_b[bk].relpath)
                ratio = SequenceMatcher(None, a_stem, b_stem).ratio()
                if ratio >= threshold:
                    candidates.append((ratio, ak, bk))
        # 贪心：分数高优先，相同分按 (a_key, b_key) 字典序稳定
        candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
        for ratio, ak, bk in candidates:
            if ak in used_a or bk in used_b:
                continue
            fuzzy_pairs.append(
                _make_pair(rem_a[ak], rem_b[bk], MATCH_FUZZY, ratio)
            )
            used_a.add(ak)
            used_b.add(bk)

    new_only_a = [sf for k, sf in rem_a.items() if k not in used_a]
    new_only_b = [sf for k, sf in rem_b.items() if k not in used_b]
    # only_* 维持按 relpath 排序的稳定输出
    new_only_a.sort(key=lambda sf: sf.relpath.lower())
    new_only_b.sort(key=lambda sf: sf.relpath.lower())

    all_pairs = list(base.pairs) + fuzzy_pairs
    all_pairs.sort(key=lambda p: p.relpath.lower())

    return PairResult(pairs=all_pairs, only_a=new_only_a, only_b=new_only_b)


def repair(
    a_map: dict[str, ScannedFile],
    b_map: dict[str, ScannedFile],
    manual_pairs: list[tuple[str, str]],
) -> PairResult:
    """按手工 (a_key, b_key) 列表重建 PairResult，全部标记 MATCH_MANUAL。

    未出现在 manual_pairs 中的 A、B 项分别进 only_a / only_b。
    重复 key 取首次出现，后续忽略。
    """
    pairs: list[FilePair] = []
    used_a: set[str] = set()
    used_b: set[str] = set()
    for ak, bk in manual_pairs:
        if ak in used_a or bk in used_b:
            continue
        if ak not in a_map or bk not in b_map:
            continue
        pairs.append(_make_pair(a_map[ak], b_map[bk], MATCH_MANUAL, 1.0))
        used_a.add(ak)
        used_b.add(bk)

    only_a = [sf for k, sf in a_map.items() if k not in used_a]
    only_b = [sf for k, sf in b_map.items() if k not in used_b]
    only_a.sort(key=lambda sf: sf.relpath.lower())
    only_b.sort(key=lambda sf: sf.relpath.lower())
    pairs.sort(key=lambda p: p.relpath.lower())
    return PairResult(pairs=pairs, only_a=only_a, only_b=only_b)


def _stem_no_ext(relpath: str) -> str:
    """取整条 relpath 去掉扩展名（保留目录段），小写化。"""
    p = PurePosixPath(relpath.lower())
    return (p.parent / p.stem).as_posix() if p.parent.as_posix() != "." else p.stem
