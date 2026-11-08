"""论文正文：arXiv 的 HTML 版（由 LaTeX 转换，结构清楚，能区分摘要、脚注、参考文献）。

两种用法：
- fetch_many(ids)：联网下载并解析（每篇间隔 3 秒）。
- load_dump(path)：读取已经提取好的段落（浏览器里用同样规则提取后导出的文件）。

只保留含 GitHub/匿名链接、或者写了"代码将会发布"的段落，不保存全文。
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from scs.models import Fragment, FullText

BASE = "https://arxiv.org/html/"
DELAY_SECONDS = 3.0
MAX_FRAGMENT_CHARS = 4000  # 摘要等长段落里链接常在结尾，上限不能太小

_LINK = re.compile(r"github\.com|4open\.science", re.IGNORECASE)
_PROMISE = re.compile(
    r"\b(?:code|codes|implementation|source|models?|data(?:set)?s?|benchmark|checkpoints?|weights)"
    r"\b[^.]{0,80}\b(?:will be|to be|upon (?:acceptance|publication)|coming soon"
    r"|after (?:the )?(?:review|acceptance|publication)"
    r"|be (?:made )?(?:publicly )?(?:released|available) (?:soon|later))",
    re.IGNORECASE,
)
# 这些 class 的元素作为一个"段落"
_BLOCK_CLASSES = (
    "ltx_p",
    "ltx_note_content",
    "ltx_bibitem",
    "ltx_caption",
    "ltx_td",
    "ltx_authors",
    "ltx_title_document",
)
# 按顺序判断段落位置，先命中的优先
_KIND_BY_ANCESTOR = (
    ("ltx_bibliography", "bib"),
    ("ltx_abstract", "abstract"),
    ("ltx_authors", "front"),
    ("ltx_title_document", "front"),
    ("ltx_note_content", "footnote"),
    ("ltx_caption", "caption"),
    ("ltx_td", "table"),
    ("ltx_appendix", "appendix"),
)
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


# ---------- 极简 DOM：只为了能找"最近的祖先" ----------


@dataclass
class _Node:
    tag: str
    classes: frozenset[str]
    href: str = ""
    parent: _Node | None = None
    children: list[_Node | str] = field(default_factory=list)

    def text(self) -> str:
        inner = "".join(c if isinstance(c, str) else c.text() for c in self.children)
        # 链接文字不是网址（例如 "here"）时，把地址插在后面，后续才能按位置判断上下文
        if self.tag == "a" and _LINK.search(self.href) and not _LINK.search(inner):
            return f"{inner} ({self.href})"
        return inner

    def ancestors(self):
        node = self
        while node is not None:
            yield node
            node = node.parent

    def descendants(self):
        for c in self.children:
            if isinstance(c, _Node):
                yield c
                yield from c.descendants()


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", frozenset())
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = _Node(tag, frozenset((a.get("class") or "").split()), a.get("href") or "", self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_endtag(self, tag):
        for node in self.cur.ancestors():  # 容忍没闭合的标签
            if node.tag == tag:
                self.cur = node.parent or self.root
                return

    def handle_data(self, data):
        self.cur.children.append(data)


def _kind(node: _Node) -> str:
    for cls, kind in _KIND_BY_ANCESTOR:
        if any(cls in a.classes for a in node.ancestors()):
            return kind
    return "body"


def _section_title(node: _Node) -> str:
    for a in node.ancestors():
        if a.tag == "section":
            for c in a.children:
                if isinstance(c, _Node) and c.tag in ("h2", "h3", "h4"):
                    return " ".join(c.text().split())[:80]
            return ""
    return ""


def parse_html(html: str) -> tuple[Fragment, ...] | None:
    """从 arXiv HTML 里提取段落。找不到论文正文时返回 None。"""
    builder = _TreeBuilder()
    builder.feed(html)
    article = next(
        (
            n
            for n in builder.root.descendants()
            if n.tag == "article" and "ltx_document" in n.classes
        ),
        None,
    )
    if article is None:
        return None
    fragments = []
    for node in article.descendants():
        if not any(c in node.classes for c in _BLOCK_CLASSES):
            continue
        hrefs = tuple(
            dict.fromkeys(
                d.href for d in node.descendants() if d.tag == "a" and _LINK.search(d.href)
            )
        )
        text = " ".join(node.text().split())
        has_link = bool(hrefs) or bool(_LINK.search(text))
        kind = _kind(node)
        if not has_link and (kind == "bib" or not _PROMISE.search(text)):
            continue
        fragments.append(Fragment(kind, _section_title(node), hrefs, text[:MAX_FRAGMENT_CHARS]))
    return tuple(fragments)


def fetch(arxiv_id: str, paper_id: str) -> FullText:
    try:
        with urllib.request.urlopen(BASE + arxiv_id, timeout=120) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return FullText(paper_id, e.code, ())
    fragments = parse_html(html)
    return FullText(paper_id, 200 if fragments is not None else 204, fragments or ())


def missing(paper_ids: list[str], existing: dict[str, FullText]) -> list[str]:
    """还没抓过正文的论文。arXiv 明确没有 HTML 版（404）的不再重试。"""
    return [
        pid
        for pid in paper_ids
        if pid not in existing or existing[pid].http_status not in (200, 404)
    ]


def fetch_many(paper_ids: list[str]) -> list[FullText]:
    results = []
    for i, pid in enumerate(paper_ids):
        if i:
            time.sleep(DELAY_SECONDS)
        results.append(fetch(pid.removeprefix("arxiv:"), pid))
    return results


def load_dump(path: Path) -> list[FullText]:
    """读取浏览器导出的文件：{"records": [{"id", "http", "blocks": [{kind, sec, hrefs, text}]}]}"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in raw["records"]:
        blocks = r.get("blocks")
        status = r["http"] if blocks is not None or r["http"] != 200 else 204
        frags = tuple(
            Fragment(b["kind"], b.get("sec", ""), tuple(b.get("hrefs", ())), b["text"])
            for b in blocks or ()
        )
        out.append(FullText(f"arxiv:{r['id']}", status, frags))
    return out
