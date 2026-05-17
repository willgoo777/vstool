from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .scanner import ScannedFile


@dataclass(frozen=True)
class FilePair:
    key: str           # 小写归一化后的相对路径
    relpath: str       # 显示用，取 B 的原始大小写（输出镜像 B）
    ext: str           # 小写扩展名，含点
    a_path: Path
    b_path: Path


@dataclass
class PairResult:
    pairs: list[FilePair] = field(default_factory=list)
    only_a: list[ScannedFile] = field(default_factory=list)
    only_b: list[ScannedFile] = field(default_factory=list)


def pair(
    a_map: dict[str, ScannedFile],
    b_map: dict[str, ScannedFile],
) -> PairResult:
    """按归一化 key 配对。输出按 relpath 排序，便于稳定显示和测试。"""
    common = sorted(set(a_map) & set(b_map))
    only_a_keys = sorted(set(a_map) - set(b_map))
    only_b_keys = sorted(set(b_map) - set(a_map))

    pairs = [
        FilePair(
            key=k,
            relpath=b_map[k].relpath,
            ext=b_map[k].abspath.suffix.lower(),
            a_path=a_map[k].abspath,
            b_path=b_map[k].abspath,
        )
        for k in common
    ]
    return PairResult(
        pairs=pairs,
        only_a=[a_map[k] for k in only_a_keys],
        only_b=[b_map[k] for k in only_b_keys],
    )
