"""从 arXiv 拿某个会议的论文：搜索备注（comment）里写了会议名的论文。

两种用法：
- ArxivSource(venue).fetch()：联网分页抓取（arXiv 要求两次请求间隔至少 3 秒）。
- ArxivSource(venue, dump=path).fetch()：读取已经保存好的原始数据，不联网。
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from scs.config import VenueConfig
from scs.models import Paper

API = "https://export.arxiv.org/api/query"
PAGE_SIZE = 500
DELAY_SECONDS = 3.5
_NS = {
    "a": "http://www.w3.org/2005/Atom",
    "x": "http://arxiv.org/schemas/atom",
    "o": "http://a9.com/-/spec/opensearch/1.1/",
}


class ArxivSource:
    def __init__(self, venue: VenueConfig, dump: Path | None = None) -> None:
        self.venue = venue
        self.dump = dump

    def fetch(self) -> list[Paper]:
        entries = load_dump(self.dump) if self.dump else self._download()
        return to_papers(entries, self.venue)

    def _download(self) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        start = 0
        while True:
            params = {
                "search_query": self.venue.arxiv_query,
                "start": start,
                "max_results": PAGE_SIZE,
                "sortBy": "submittedDate",
                "sortOrder": "ascending",
            }
            url = f"{API}?{urllib.parse.urlencode(params)}"
            with urllib.request.urlopen(url, timeout=60) as resp:
                page, total = parse_atom(resp.read().decode("utf-8"))
            entries.extend(page)
            start += PAGE_SIZE
            if not page or start >= total:
                return entries
            time.sleep(DELAY_SECONDS)


def load_dump(path: Path) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))["entries"]


def parse_atom(xml_text: str) -> tuple[list[dict[str, str]], int]:
    """解析 arXiv API 返回的一页 Atom XML，返回 (条目列表, 总条数)。"""
    root = ET.fromstring(xml_text)
    total = int(root.findtext("o:totalResults", default="0", namespaces=_NS))
    entries = []
    for e in root.findall("a:entry", _NS):

        def text(tag: str, entry: ET.Element = e) -> str:
            return " ".join((entry.findtext(tag, default="", namespaces=_NS)).split())

        entries.append(
            {
                "id": text("a:id").removeprefix("http://arxiv.org/abs/"),
                "title": text("a:title"),
                "published": text("a:published"),
                "summary": text("a:summary"),
                "comment": text("x:comment"),
            }
        )
    return entries, total


def is_accepted(comment: str, venue: VenueConfig) -> bool:
    """逐句判断：只要有一句提到了会议名、且同一句里没有"在审""workshop""被拒"这类词，就算录用。

    逐句是为了避免误伤，例如 "Accepted at ICLR 2025. Earlier version at a NeurIPS workshop."
    """
    for clause in _CLAUSE_SPLIT.split(comment):
        if any(p.search(clause) for p in venue.include) and not any(
            p.search(clause) for p in venue.exclude
        ):
            return True
    return False


_CLAUSE_SPLIT = re.compile(r"[.;|\n]\s+|[;|\n]")


def strip_version(arxiv_id: str) -> str:
    """2302.02182v3 -> 2302.02182"""
    head, sep, tail = arxiv_id.rpartition("v")
    return head if sep and tail.isdigit() and head else arxiv_id


def to_papers(entries: list[dict[str, str]], venue: VenueConfig) -> list[Paper]:
    papers: dict[str, Paper] = {}
    for e in entries:
        if not is_accepted(e["comment"], venue):
            continue
        aid = strip_version(e["id"])
        papers[aid] = Paper(
            paper_id=f"arxiv:{aid}",
            venue=venue.key,
            title=e["title"],
            url=f"https://arxiv.org/abs/{aid}",
            published=e["published"][:10],
            text=f"{e['summary']}\n{e['comment']}",
        )
    return sorted(papers.values(), key=lambda p: p.paper_id)
