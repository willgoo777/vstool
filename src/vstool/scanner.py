from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .config import EXCLUDE_NAME_PREFIXES, EXCLUDE_SUFFIXES, SUPPORTED_EXTS


@dataclass(frozen=True)
class ScannedFile:
    relpath: str       # 相对 root，统一 posix 风格、原始大小写
    abspath: Path


def _is_excluded(name: str) -> bool:
    if name.startswith(EXCLUDE_NAME_PREFIXES):
        return True
    lower = name.lower()
    if any(lower.endswith(s) for s in EXCLUDE_SUFFIXES):
        return True
    return False


def scan(
    root: Path,
    allowed_exts: Iterable[str] = SUPPORTED_EXTS,
) -> dict[str, ScannedFile]:
    """递归扫描 root，返回 { 规范化 key: ScannedFile }。

    key 为 relpath.lower()（posix 风格），用于跨平台、大小写不敏感的配对。
    """
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"目录不存在：{root}")

    allowed = {e.lower() for e in allowed_exts}
    result: dict[str, ScannedFile] = {}

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if _is_excluded(p.name):
            continue
        if p.suffix.lower() not in allowed:
            continue
        rel = p.relative_to(root).as_posix()
        key = rel.lower()
        result[key] = ScannedFile(relpath=rel, abspath=p.resolve())

    return result
