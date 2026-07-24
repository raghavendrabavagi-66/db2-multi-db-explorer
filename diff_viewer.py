"""Side-by-side HTML diff for DDL comparison."""

from __future__ import annotations

import html
import difflib


def _line_class(tag: str) -> str:
    if tag == "insert":
        return "diff-add"
    if tag == "delete":
        return "diff-del"
    return "diff-ctx"


def side_by_side_diff_html(left: str, right: str, left_title: str = "GitLab", right_title: str = "Database") -> str:
    left_lines = (left or "").splitlines()
    right_lines = (right or "").splitlines()
    matcher = difflib.SequenceMatcher(None, left_lines, right_lines)

    left_rows: list[str] = []
    right_rows: list[str] = []
    ln_left = 1
    ln_right = 1

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                left_rows.append(
                    f'<tr><td class="ln">{ln_left}</td><td class="diff-ctx">{html.escape(left_lines[i])}</td></tr>'
                )
                ln_left += 1
            for j in range(j1, j2):
                right_rows.append(
                    f'<tr><td class="ln">{ln_right}</td><td class="diff-ctx">{html.escape(right_lines[j])}</td></tr>'
                )
                ln_right += 1
        elif tag == "replace":
            for i in range(i1, i2):
                left_rows.append(
                    f'<tr><td class="ln">{ln_left}</td><td class="diff-del">{html.escape(left_lines[i])}</td></tr>'
                )
                ln_left += 1
            for j in range(j1, j2):
                right_rows.append(
                    f'<tr><td class="ln">{ln_right}</td><td class="diff-add">{html.escape(right_lines[j])}</td></tr>'
                )
                ln_right += 1
        elif tag == "delete":
            for i in range(i1, i2):
                left_rows.append(
                    f'<tr><td class="ln">{ln_left}</td><td class="diff-del">{html.escape(left_lines[i])}</td></tr>'
                )
                ln_left += 1
        elif tag == "insert":
            for j in range(j1, j2):
                right_rows.append(
                    f'<tr><td class="ln">{ln_right}</td><td class="diff-add">{html.escape(right_lines[j])}</td></tr>'
                )
                ln_right += 1

    pad = max(len(left_rows), len(right_rows))
    while len(left_rows) < pad:
        left_rows.append('<tr><td class="ln">&nbsp;</td><td class="diff-ctx">&nbsp;</td></tr>')
    while len(right_rows) < pad:
        right_rows.append('<tr><td class="ln">&nbsp;</td><td class="diff-ctx">&nbsp;</td></tr>')

    return f"""
<style>
.diff-wrap {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }}
.diff-head {{ font-weight: 600; padding: 6px 8px; background: #f0f0f0; border-bottom: 1px solid #ddd; }}
.diff-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 1px solid #ddd; border-radius: 6px; overflow: hidden; }}
.diff-pane {{ overflow: auto; max-height: 420px; }}
.diff-pane table {{ width: 100%; border-collapse: collapse; }}
.diff-pane td {{ padding: 1px 6px; vertical-align: top; white-space: pre-wrap; word-break: break-word; }}
.ln {{ color: #888; width: 36px; text-align: right; user-select: none; border-right: 1px solid #eee; background: #fafafa; }}
.diff-add {{ background: #d4edda; }}
.diff-del {{ background: #f8d7da; }}
.diff-ctx {{ background: #fff; }}
</style>
<div class="diff-wrap">
  <div class="diff-grid">
    <div class="diff-pane">
      <div class="diff-head">{html.escape(left_title)}</div>
      <table>{''.join(left_rows)}</table>
    </div>
    <div class="diff-pane">
      <div class="diff-head">{html.escape(right_title)}</div>
      <table>{''.join(right_rows)}</table>
    </div>
  </div>
</div>
"""


def count_diff_hunks(left: str, right: str) -> int:
    left_lines = (left or "").splitlines()
    right_lines = (right or "").splitlines()
    hunks = 0
    for tag, _, _, _, _ in difflib.SequenceMatcher(None, left_lines, right_lines).get_opcodes():
        if tag != "equal":
            hunks += 1
    return hunks
