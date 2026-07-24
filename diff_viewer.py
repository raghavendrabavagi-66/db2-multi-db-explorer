"""Side-by-side HTML diff for DDL comparison."""

from __future__ import annotations

import html
import difflib
import re

from ddl_normalizer import strip_comments_and_headers

_DIFF_STYLES = """
.diff-wrap { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
.diff-head { font-weight: 600; padding: 6px 8px; background: #f0f0f0; border-bottom: 1px solid #ddd; }
.diff-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0; border: 1px solid #ddd; border-radius: 6px; overflow: hidden; }
.diff-pane { overflow: auto; max-height: calc(40vh - 9rem); min-height: 200px; min-width: 0; }
.diff-pane table { width: 100%; border-collapse: collapse; }
.diff-pane td { padding: 1px 6px; vertical-align: top; white-space: pre-wrap; word-break: break-word; }
.ln { color: #888; width: 36px; text-align: right; user-select: none; border-right: 1px solid #eee; background: #fafafa; }
.diff-add { background: #d4edda; }
.diff-del { background: #f8d7da; }
.diff-ctx { background: #fff; }
.diff-empty { background: #fafafa; color: #bbb; }
.diff-inline-add { background: #d4edda; border-radius: 2px; }
.diff-inline-del { background: #f8d7da; border-radius: 2px; }
"""

_BLANK = "&nbsp;"


def prepare_display_ddl(text: str) -> str:
    """Strip comments/noise before showing DDL in the diff pane."""
    if not (text or "").strip():
        return ""
    cleaned = strip_comments_and_headers(text)
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    if lines:
        return "\n".join(lines)
    # Fallback: keep non-comment lines from raw text (handles odd encodings / markers)
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    return "\n".join(raw_lines)


def _normalize_phrases(text: str) -> str:
    text = re.sub(r"\bNO ACTION\b", "NO_ACTION", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSET NULL\b", "SET_NULL", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSET DEFAULT\b", "SET_DEFAULT", text, flags=re.IGNORECASE)
    return text


def _display_token(token: str) -> str:
    return (
        token.replace("NO_ACTION", "NO ACTION")
        .replace("SET_NULL", "SET NULL")
        .replace("SET_DEFAULT", "SET DEFAULT")
    )


def _tokenize_ddl(text: str) -> list[str]:
    normalized = _normalize_phrases(text)
    return re.findall(
        r"\[[^\]]+\]|NO_ACTION|SET_NULL|SET_DEFAULT|\w+|[^\w\s]",
        normalized,
    )


def _inline_diff_html(left: str, right: str) -> tuple[str, str]:
    """Highlight only differing tokens within two lines."""
    left_tokens = _tokenize_ddl(left)
    right_tokens = _tokenize_ddl(right)
    matcher = difflib.SequenceMatcher(None, left_tokens, right_tokens)

    left_html: list[str] = []
    right_html: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for token in left_tokens[i1:i2]:
                left_html.append(html.escape(_display_token(token)))
            for token in right_tokens[j1:j2]:
                right_html.append(html.escape(_display_token(token)))
        elif tag == "replace":
            if left_tokens[i1:i2]:
                chunk = " ".join(html.escape(_display_token(t)) for t in left_tokens[i1:i2])
                left_html.append(f'<span class="diff-inline-del">{chunk}</span>')
            if right_tokens[j1:j2]:
                chunk = " ".join(html.escape(_display_token(t)) for t in right_tokens[j1:j2])
                right_html.append(f'<span class="diff-inline-add">{chunk}</span>')
        elif tag == "delete":
            chunk = " ".join(html.escape(_display_token(t)) for t in left_tokens[i1:i2])
            left_html.append(f'<span class="diff-inline-del">{chunk}</span>')
        elif tag == "insert":
            chunk = " ".join(html.escape(_display_token(t)) for t in right_tokens[j1:j2])
            right_html.append(f'<span class="diff-inline-add">{chunk}</span>')

    return " ".join(left_html), " ".join(right_html)


def _row(ln: int, content: str, cell_class: str = "diff-ctx") -> str:
    return f'<tr><td class="ln">{ln}</td><td class="{cell_class}">{content}</td></tr>'


def _blank_row(ln: int) -> str:
    return _row(ln, _BLANK, "diff-empty")


def side_by_side_diff_html(
    left: str,
    right: str,
    left_title: str = "GitLab",
    right_title: str = "Database",
) -> str:
    left_lines = prepare_display_ddl(left).splitlines()
    right_lines = prepare_display_ddl(right).splitlines()

    if not left_lines and (left or "").strip():
        left_lines = [ln.strip() for ln in left.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    if not right_lines and (right or "").strip():
        right_lines = [ln.strip() for ln in right.splitlines() if ln.strip() and not ln.strip().startswith("--")]

    matcher = difflib.SequenceMatcher(None, left_lines, right_lines)

    left_rows: list[str] = []
    right_rows: list[str] = []
    ln_left = 1
    ln_right = 1

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                left_rows.append(_row(ln_left, html.escape(left_lines[i])))
                right_rows.append(_row(ln_right, html.escape(right_lines[j])))
                ln_left += 1
                ln_right += 1
        elif tag == "replace":
            left_chunk = left_lines[i1:i2]
            right_chunk = right_lines[j1:j2]
            if len(left_chunk) == 1 and len(right_chunk) == 1:
                l_html, r_html = _inline_diff_html(left_chunk[0], right_chunk[0])
                left_rows.append(_row(ln_left, l_html))
                right_rows.append(_row(ln_right, r_html))
                ln_left += 1
                ln_right += 1
            else:
                max_len = max(len(left_chunk), len(right_chunk))
                for idx in range(max_len):
                    l_line = left_chunk[idx] if idx < len(left_chunk) else ""
                    r_line = right_chunk[idx] if idx < len(right_chunk) else ""
                    if l_line and r_line:
                        l_html, r_html = _inline_diff_html(l_line, r_line)
                        left_rows.append(_row(ln_left, l_html))
                        right_rows.append(_row(ln_right, r_html))
                    elif l_line:
                        left_rows.append(_row(ln_left, html.escape(l_line), "diff-del"))
                        right_rows.append(_blank_row(ln_right))
                    elif r_line:
                        left_rows.append(_blank_row(ln_left))
                        right_rows.append(_row(ln_right, html.escape(r_line), "diff-add"))
                    ln_left += 1
                    ln_right += 1
        elif tag == "delete":
            for i in range(i1, i2):
                left_rows.append(_row(ln_left, html.escape(left_lines[i]), "diff-del"))
                right_rows.append(_blank_row(ln_right))
                ln_left += 1
                ln_right += 1
        elif tag == "insert":
            for j in range(j1, j2):
                left_rows.append(_blank_row(ln_left))
                right_rows.append(_row(ln_right, html.escape(right_lines[j]), "diff-add"))
                ln_left += 1
                ln_right += 1

    if not left_rows and not right_rows:
        left_rows.append(_row(1, _BLANK, "diff-empty"))
        right_rows.append(_row(1, _BLANK, "diff-empty"))

    return f"""
<style>
{_DIFF_STYLES}
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
    left_lines = prepare_display_ddl(left).splitlines()
    right_lines = prepare_display_ddl(right).splitlines()
    hunks = 0
    for tag, _, _, _, _ in difflib.SequenceMatcher(None, left_lines, right_lines).get_opcodes():
        if tag != "equal":
            hunks += 1
    return hunks
