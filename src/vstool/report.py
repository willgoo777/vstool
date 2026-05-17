"""summary.html 生成。纯字符串拼接 + 内联 CSS，不依赖模板引擎。"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from pathlib import Path

from .config import SUMMARY_FILENAME
from .i18n import T

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"

_STATUS_LABEL = {
    STATUS_OK: T["summary_status_ok"],
    STATUS_FAIL: T["summary_status_fail"],
    STATUS_SKIP: T["summary_status_skip"],
}

_STATUS_CLASS = {
    STATUS_OK: "ok",
    STATUS_FAIL: "fail",
    STATUS_SKIP: "skip",
}


@dataclass
class PairOutcome:
    relpath: str
    status: str           # STATUS_OK / STATUS_FAIL / STATUS_SKIP
    output_path: Path | None = None
    reason: str = ""


@dataclass
class PipelineResult:
    outcomes: list[PairOutcome] = field(default_factory=list)
    only_a: list[str] = field(default_factory=list)
    only_b: list[str] = field(default_factory=list)
    summary_path: Path | None = None
    cancelled: bool = False

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def ok_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == STATUS_OK)

    @property
    def fail_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == STATUS_FAIL)

    @property
    def skip_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == STATUS_SKIP)


_CSS = """
body { font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
       margin: 24px; color: #222; }
h1 { font-size: 22px; margin-bottom: 8px; }
h2 { font-size: 16px; margin-top: 28px; border-bottom: 1px solid #ddd;
     padding-bottom: 4px; }
.kv { display: grid; grid-template-columns: 160px auto;
      row-gap: 4px; column-gap: 12px; font-size: 14px; max-width: 480px; }
.kv .v { font-weight: 600; }
table { border-collapse: collapse; width: 100%; font-size: 13px;
        margin-top: 8px; }
th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left;
         vertical-align: top; }
th { background: #f4f4f4; }
tr:nth-child(even) td { background: #fafafa; }
.status { font-weight: 600; }
.status.ok   { color: #1b873f; }
.status.fail { color: #c0392b; }
.status.skip { color: #b27600; }
.empty { color: #888; font-style: italic; }
.path { font-family: ui-monospace, Consolas, "Microsoft YaHei Mono", monospace;
        font-size: 12px; word-break: break-all; }
""".strip()


def _h(s: object) -> str:
    return html.escape("" if s is None else str(s))


def _link(p: Path | None) -> str:
    if p is None:
        return f'<span class="empty">{_h(T["summary_empty"])}</span>'
    return f'<a class="path" href="{p.as_uri()}">{_h(T["summary_open"])}</a>'


def _list_table(items: list[str]) -> str:
    if not items:
        return f'<p class="empty">{_h(T["summary_empty"])}</p>'
    rows = "\n".join(
        f"<tr><td class='path'>{_h(p)}</td></tr>" for p in items
    )
    return (f"<table><thead><tr><th>{_h(T['summary_col_name'])}</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>")


def _pairs_table(outcomes: list[PairOutcome]) -> str:
    if not outcomes:
        return f'<p class="empty">{_h(T["summary_empty"])}</p>'
    rows = []
    for o in outcomes:
        cls = _STATUS_CLASS.get(o.status, "")
        label = _STATUS_LABEL.get(o.status, o.status)
        rows.append(
            "<tr>"
            f"<td class='path'>{_h(o.relpath)}</td>"
            f"<td class='status {cls}'>{_h(label)}</td>"
            f"<td>{_link(o.output_path)}</td>"
            f"<td>{_h(o.reason)}</td>"
            "</tr>"
        )
    head = (
        f"<th>{_h(T['summary_col_name'])}</th>"
        f"<th>{_h(T['summary_col_status'])}</th>"
        f"<th>{_h(T['summary_col_output'])}</th>"
        f"<th>{_h(T['summary_col_reason'])}</th>"
    )
    return (f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def write_html_summary(out_dir: Path, result: PipelineResult) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / SUMMARY_FILENAME
    overview = (
        '<div class="kv">'
        f'<div>{_h(T["summary_total"])}</div><div class="v">{result.total}</div>'
        f'<div>{_h(T["summary_ok"])}</div><div class="v">{result.ok_count}</div>'
        f'<div>{_h(T["summary_fail"])}</div><div class="v">{result.fail_count}</div>'
        f'<div>{_h(T["summary_skip"])}</div><div class="v">{result.skip_count}</div>'
        "</div>"
    )
    html_doc = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>{_h(T["summary_title"])}</title>'
        f"<style>{_CSS}</style></head><body>"
        f'<h1>{_h(T["summary_title"])}</h1>'
        f'<h2>{_h(T["summary_overview"])}</h2>{overview}'
        f'<h2>{_h(T["summary_pairs"])}</h2>{_pairs_table(result.outcomes)}'
        f'<h2>{_h(T["summary_only_a"])}</h2>{_list_table(result.only_a)}'
        f'<h2>{_h(T["summary_only_b"])}</h2>{_list_table(result.only_b)}'
        "</body></html>"
    )
    path.write_text(html_doc, encoding="utf-8")
    return path
