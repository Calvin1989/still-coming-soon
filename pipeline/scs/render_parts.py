"""网页上的各个组成部分：方格图、图例、论文条目。纯函数，输入数据，输出 HTML 字符串。"""

from __future__ import annotations

import re
from html import escape
from typing import Any

# 方格图和列表里的顺序
WAFFLE_ORDER = ("empty", "partial", "gone", "data_only", "unknown", "released")
LIST_ORDER = ("empty", "partial", "gone", "no_repo", "data_only", "unknown", "released")
# "未兑现"只算能确认的情况（见规则说明页）
UNDELIVERED = ("empty", "partial", "gone")

# 论文原话里用荧光笔标出的部分：说代码在哪里/会不会发布的那几个词
_AVAILABILITY = re.compile(
    r"(?:(?:will|would|shall)\s+be\s+|is\s+|are\s+|has\s+been\s+|have\s+been\s+|be\s+)?"
    r"(?:made\s+)?(?:publicly\s+|freely\s+|openly\s+)?"
    r"(?:available|released|open[- ]?sourced|provided|accessible|published)"
    r"(?:\s+(?:at|in|on|via|here|soon|upon acceptance|upon publication))?"
    r"|can\s+be\s+found(?:\s+(?:at|in|here))?|coming\s+soon|(?<![\w])(?:code|project)\s*:",
    re.IGNORECASE,
)


_TEX_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "varphi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ",
    "Lambda": "Λ", "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω", "ell": "ℓ",
    "infty": "∞", "times": "×", "cdot": "·", "pm": "±", "to": "→", "rightarrow": "→",
    "leftarrow": "←", "leftrightarrow": "↔", "sim": "∼", "approx": "≈", "le": "≤", "leq": "≤",
    "ge": "≥", "geq": "≥", "&": "&", "%": "%", "_": "_",
}  # fmt: skip
_TEX_STYLE = re.compile(
    r"\\(?:mathbf|mathcal|mathrm|mathbb|mathsf|mathit|boldsymbol|bm|text\w*|emph|operatorname)"
    r"\s*\{([^{}]*)\}"
)
_SUPERSCRIPT = str.maketrans("0123456789+-n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ")
_SUBSCRIPT = str.maketrans("0123456789+-", "₀₁₂₃₄₅₆₇₈₉₊₋")


def _tex_script(text: str, table: dict[int, str], mark: str) -> str:
    """能用上标/下标字符表示的就换掉，否则保留原样。"""
    return text.translate(table) if all(ord(c) in table for c in text) else mark + text


def tidy_title(title: str) -> str:
    """把标题里的 LaTeX 变成能读的文字：A$^3$ → A³，$\\beta$-DPO → β-DPO。"""

    def math(m: re.Match[str]) -> str:
        t = _TEX_STYLE.sub(r"\1", m.group(1))
        t = re.sub(
            r"\^\{([^{}]*)\}|\^(\S)",
            lambda x: _tex_script(x.group(1) or x.group(2), _SUPERSCRIPT, "^"),
            t,
        )
        t = re.sub(
            r"_\{([^{}]*)\}|_(\S)",
            lambda x: _tex_script(x.group(1) or x.group(2), _SUBSCRIPT, "_"),
            t,
        )
        t = re.sub(r"\\([A-Za-z]+|[&%_])", lambda x: _TEX_GREEK.get(x.group(1), x.group(1)), t)
        return " ".join(t.replace("{", "").replace("}", "").split())

    title = _TEX_STYLE.sub(r"\1", title)
    return re.sub(r"\$([^$]+)\$", math, title).replace("\\", "")


def entry_status(row: dict[str, Any]) -> str:
    """把 build 的状态归成网页上的类别：匿名链接和没有仓库链接合并为 no_repo。"""
    return "no_repo" if row["status"] in ("anonymous", "no_link") else row["status"]


def marked(text: str, pattern: re.Pattern[str] = _AVAILABILITY) -> str:
    """转义文本，并把第一处命中的词用 <mark> 包起来。"""
    m = pattern.search(text)
    if not m or not m.group(0).strip():
        return escape(text)
    return f"{escape(text[: m.start()])}<mark>{escape(m.group(0))}</mark>{escape(text[m.end() :])}"


def human_size(n: int, too_big: str) -> str:
    if n < 0:
        return too_big
    if n < 1000:
        return f"{n} B"
    if n < 1_000_000:
        return f"{n / 1000:.1f} KB"
    return f"{n / 1_000_000:.1f} MB"


def entry_id(paper_id: str) -> str:
    return "p-" + re.sub(r"[^\w.-]", "-", paper_id.removeprefix("arxiv:"))


# ---------- 方格图和图例 ----------


def waffle(rows: list[dict[str, Any]], t: dict[str, Any], href_prefix: str = "") -> str:
    rank = {s: i for i, s in enumerate(WAFFLE_ORDER)}
    cells = sorted(
        (r for r in rows if entry_status(r) in rank),
        key=lambda r: (rank[entry_status(r)], -r["promised_days"]),
    )
    parts = []
    for r in cells:
        status = entry_status(r)
        label = escape(f"{tidy_title(r['title'])} ({t['status'][status]})")
        parts.append(
            f'<a class="cell {status}" href="{href_prefix}#{entry_id(r["paper_id"])}" '
            f'title="{label}" aria-label="{label}" tabindex="-1"></a>'
        )
    return f'<div class="waffle">{"".join(parts)}</div>'


def legend(counts: dict[str, int], t: dict[str, Any], checklist: int = 0) -> str:
    """checklist：已开源但作者清单没勾完的论文数。补充信息，单独一个按钮，默认不按下。"""
    items = []
    for status in (*UNDELIVERED, "data_only", "no_repo", "released"):
        n = counts.get(status, 0)
        if not n:
            continue
        pressed = "true" if status in UNDELIVERED else "false"
        items.append(
            f'<li><button type="button" data-statuses="{status}" aria-pressed="{pressed}">'
            f'<span class="cell {status}"></span>{escape(t["status"][status])} <b>{n}</b>'
            f"</button></li>"
        )
    if checklist:
        items.append(
            f'<li class="extra"><button type="button" data-statuses="checklist" '
            f'aria-pressed="false"><span class="cell checklist"></span>'
            f"{escape(t['checklist_legend'])} <b>{checklist}</b></button></li>"
        )
    return f'<ul class="legend">{"".join(items)}</ul>'


# ---------- 论文条目 ----------


def _said(sentence: str, t: dict[str, Any]) -> str:
    if not sentence:
        return ""
    return (
        f'<figure class="said"><figcaption>{escape(t["said"])}</figcaption>'
        f"<blockquote>{marked(sentence)}</blockquote></figure>"
    )


def _listing(row: dict[str, Any], t: dict[str, Any]) -> str:
    listing = row.get("listing") or []
    if not listing:
        n = row.get("file_count", 0)
        return f'<p class="absent">{escape(t["files_more"].format(n=n))}</p>'
    shown = listing[:8]
    lines = "".join(
        f"<tr><td>{escape(path)}</td><td>{escape(human_size(size, t['too_big']))}</td></tr>"
        for path, size in shown
    )
    more = len(listing) - len(shown)
    if more:
        lines += f"<tr><td>{escape(t['files_more'].format(n=f'+{more}'))}</td><td></td></tr>"
    return f"<table>{lines}</table>"


def _has(row: dict[str, Any], status: str, t: dict[str, Any], promise: re.Pattern[str]) -> str:
    if status == "no_repo":
        if row["status"] == "anonymous":
            link = escape(row["evidence"])
            body = (
                f'<p class="absent">{escape(t["anonymous_text"])} '
                f'<a href="https://{link}">{link}</a></p>'
            )
        else:
            body = f'<p class="absent">{escape(t["no_link_text"])}</p>'
        return (
            f'<figure class="has"><figcaption>{escape(t["has_plain"])}</figcaption>'
            f'<div class="box">{body}</div></figure>'
        )
    repo = escape(row["repo"])
    repo_link = f'<a href="https://github.com/{repo}">{repo}</a>'
    caption = t["has"].format(repo=repo_link)
    if status == "gone":
        inner = f'<p class="absent">{escape(t["gone_text"])}</p>'
    else:
        inner = _listing(row, t)
        if row.get("last_commit"):
            inner += (
                f'<p class="note">{escape(t["last_commit"].format(date=row["last_commit"]))}</p>'
            )
    if row.get("linked_repo"):
        inner += f'<p class="note">{escape(t["fallback_note"].format(repo=row["linked_repo"]))}</p>'
    readme = ""
    if row.get("promise_text"):
        readme = (
            f'<p class="readme"><span>{escape(t["readme_says"])}</span><br>'
            f"{marked(row['promise_text'], promise)}</p>"
        )
    return (
        f'<figure class="has"><figcaption>{caption}</figcaption>'
        f'<div class="box">{inner}</div>{readme}</figure>'
    )


def _checklist(row: dict[str, Any], t: dict[str, Any]) -> str:
    """作者在 README 里列的发布清单还没勾完（补充信息）。只陈述清单原文，不下结论。"""
    c = row.get("checklist")
    if not c:
        return ""
    items = "".join(f"<li>{escape(text)}</li>" for text in c["open"])
    note = t["checklist_note"].format(done=c["done"], total=c["total"])
    return f'<div class="checklist"><p>{escape(note)}</p><ul>{items}</ul></div>'


def _sub(row: dict[str, Any], status: str, t: dict[str, Any]) -> str:
    """标题下面那一行：仓库名；没有仓库时说明情况。"""
    if row.get("repo"):
        return f'<span class="repo">{escape(row["repo"])}</span>'
    if row["status"] == "anonymous":
        return f'<span class="repo">{escape(row["evidence"])}</span>'
    return f'<span class="repo none">{escape(t["no_link_short"])}</span>'


def entry(row: dict[str, Any], t: dict[str, Any], promise: re.Pattern[str]) -> str:
    """一篇论文占一行；没兑现的可以点开，看论文原话和仓库里实际有什么。

    用 <details>，没有脚本也能展开。已开源的论文只有一行，标题和仓库都是链接。
    """
    status = entry_status(row)
    title = tidy_title(row["title"])
    search = escape(f"{title} {row['title']} {row.get('repo', '')}".lower())
    extra = ' data-extra="checklist"' if row.get("checklist") else ""
    cell = f'<span class="cell {status}" aria-hidden="true"></span>'
    attrs = f'id="{entry_id(row["paper_id"])}" data-status="{status}"{extra} data-search="{search}"'
    if status == "released":
        repo = escape(row["repo"])
        return (
            f'<li class="entry plain" {attrs}><div class="row">{cell}<span class="what">'
            f'<a class="title" href="{escape(row["url"])}">{escape(title)}</a>'
            f'<a class="repo" href="https://github.com/{repo}">{repo}</a></span></div>'
            f"{_checklist(row, t)}</li>"
        )
    days = escape(t["days_after"].format(d=row["promised_days"]))
    sentence = row.get("paper_sentence") or (
        row.get("evidence") if row["status"] == "no_link" else ""
    )
    return (
        f'<li class="entry" {attrs}><details><summary>{cell}<span class="what">'
        f'<span class="title">{escape(title)}</span>{_sub(row, status, t)}</span>'
        f'<span class="chev" aria-hidden="true"></span></summary>'
        f'<div class="body"><p class="paper"><a href="{escape(row["url"])}">'
        f"{escape(t['paper_link'])}</a> · {days}</p>"
        f'<div class="evidence">{_said(sentence, t)}{_has(row, status, t, promise)}</div>'
        f"{_checklist(row, t)}</div></details></li>"
    )


def entry_groups(rows: list[dict[str, Any]], t: dict[str, Any], promise: re.Pattern[str]) -> str:
    """按状态分组，每组一个小标题（颜色和方格图一致）。"""
    out = []
    for status in LIST_ORDER:
        group = [r for r in rows if entry_status(r) == status]
        if not group:
            continue
        items = "\n".join(entry(r, t, promise) for r in group)
        out.append(
            f'<section class="group" data-group="{status}"><h2 class="group-head">'
            f'<span class="cell {status}" aria-hidden="true"></span>'
            f"{escape(t['status'][status])} <b>{len(group)}</b></h2>"
            f'<ul class="entries">\n{items}\n</ul></section>'
        )
    return "".join(out)


def all_rows(site: dict[str, Any]) -> list[dict[str, Any]]:
    """有仓库的和没有仓库的合成一个列表，按 LIST_ORDER 和天数排序。"""
    rows = site["rows"] + [{**r, "status": r["kind"]} for r in site["no_repo"]]
    rank = {s: i for i, s in enumerate(LIST_ORDER)}
    return sorted(rows, key=lambda r: (rank[entry_status(r)], -r["promised_days"], r["title"]))


def counts_of(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        s = entry_status(r)
        counts[s] = counts.get(s, 0) + 1
    return counts
