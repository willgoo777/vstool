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
    has_diff: bool | None = None   # None=失败/跳过；True=有差异；False=无差异
    notice: str = ""               # 成功状态下的提示（如「已自动接受 N 处修订」）


@dataclass
class PipelineResult:
    outcomes: list[PairOutcome] = field(default_factory=list)
    only_a: list[str] = field(default_factory=list)
    only_b: list[str] = field(default_factory=list)
    summary_path: Path | None = None
    cancelled: bool = False
    a_total: int = 0
    b_total: int = 0

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def ok_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == STATUS_OK)

    @property
    def ok_with_diff(self) -> int:
        return sum(1 for o in self.outcomes
                   if o.status == STATUS_OK and o.has_diff is True)

    @property
    def ok_no_diff(self) -> int:
        return sum(1 for o in self.outcomes
                   if o.status == STATUS_OK and o.has_diff is False)

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
.kv { display: grid; grid-template-columns: 200px auto;
      row-gap: 4px; column-gap: 12px; font-size: 14px; max-width: 520px; }
.kv .v { font-weight: 600; }
.hint { color: #555; font-size: 13px; margin: 6px 0 0; }
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
.notice { color: #666; font-size: 12px; font-style: italic; }
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


def _ok_table(outcomes: list[PairOutcome], *, show_notice: bool) -> str:
    """成功段（有差异/无差异）共用：文件、对比结果链接，可选提示列。"""
    if not outcomes:
        return f'<p class="empty">{_h(T["summary_empty"])}</p>'
    head = (
        f"<th>{_h(T['summary_col_name'])}</th>"
        f"<th>{_h(T['summary_col_output'])}</th>"
    )
    if show_notice:
        head += f"<th>{_h(T['summary_col_notice'])}</th>"
    rows: list[str] = []
    for o in outcomes:
        cells = (
            f"<td class='path'>{_h(o.relpath)}</td>"
            f"<td>{_link(o.output_path)}</td>"
        )
        if show_notice:
            cells += f"<td class='notice'>{_h(o.notice)}</td>"
        rows.append(f"<tr>{cells}</tr>")
    return (f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def _failed_table(outcomes: list[PairOutcome]) -> str:
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
            f"<td>{_h(o.reason)}</td>"
            "</tr>"
        )
    head = (
        f"<th>{_h(T['summary_col_name'])}</th>"
        f"<th>{_h(T['summary_col_status'])}</th>"
        f"<th>{_h(T['summary_col_reason'])}</th>"
    )
    return (f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>")


def write_html_summary(out_dir: Path, result: PipelineResult) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / SUMMARY_FILENAME

    with_diff = [o for o in result.outcomes
                 if o.status == STATUS_OK and o.has_diff is True]
    no_diff = [o for o in result.outcomes
               if o.status == STATUS_OK and o.has_diff is False]
    failed = [o for o in result.outcomes
              if o.status in (STATUS_FAIL, STATUS_SKIP)]

    overview = (
        '<div class="kv">'
        f'<div>{_h(T["summary_a_total"])}</div><div class="v">{result.a_total}</div>'
        f'<div>{_h(T["summary_b_total"])}</div><div class="v">{result.b_total}</div>'
        f'<div>{_h(T["summary_total"])}</div><div class="v">{result.total}</div>'
        f'<div>{_h(T["summary_only_a"])}</div><div class="v">{len(result.only_a)}</div>'
        f'<div>{_h(T["summary_only_b"])}</div><div class="v">{len(result.only_b)}</div>'
        f'<div>{_h(T["summary_ok_with_diff"])}</div><div class="v">{result.ok_with_diff}</div>'
        f'<div>{_h(T["summary_ok_no_diff"])}</div><div class="v">{result.ok_no_diff}</div>'
        f'<div>{_h(T["summary_fail"])}</div><div class="v">{result.fail_count}</div>'
        f'<div>{_h(T["summary_skip"])}</div><div class="v">{result.skip_count}</div>'
        "</div>"
    )

    diff_section = (
        f'<h2>{_h(T["summary_section_with_diff"])}（{len(with_diff)}）</h2>'
        f'<p class="hint">{_h(T["summary_diff_hint"])}</p>'
        f'{_ok_table(with_diff, show_notice=True)}'
    )
    nodiff_section = (
        f'<h2>{_h(T["summary_section_no_diff"])}（{len(no_diff)}）</h2>'
        f'{_ok_table(no_diff, show_notice=True)}'
    )
    failed_section = (
        f'<h2>{_h(T["summary_section_failed"])}（{len(failed)}）</h2>'
        f'{_failed_table(failed)}'
    )

    html_doc = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<title>{_h(T["summary_title"])}</title>'
        f"<style>{_CSS}</style></head><body>"
        f'<h1>{_h(T["summary_title"])}</h1>'
        f'<h2>{_h(T["summary_overview"])}</h2>{overview}'
        f'{diff_section}'
        f'{nodiff_section}'
        f'{failed_section}'
        f'<h2>{_h(T["summary_only_a"])}</h2>{_list_table(result.only_a)}'
        f'<h2>{_h(T["summary_only_b"])}</h2>{_list_table(result.only_b)}'
        "</body></html>"
    )
    path.write_text(html_doc, encoding="utf-8")
    return path
