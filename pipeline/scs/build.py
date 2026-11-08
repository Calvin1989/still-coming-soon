"""把论文、链接、仓库检查结果合在一起，生成网站要用的数据。纯函数。"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from scs.classify import classify
from scs.config import ClassifyConfig, VenueConfig
from scs.links import anonymous_link, promise_without_link
from scs.models import FullText, Paper, RepoLink, RepoSnapshot, Status

_STATUS_ORDER = {
    Status.EMPTY.value: 0,
    Status.GONE.value: 1,
    Status.PARTIAL.value: 2,
    Status.DATA_ONLY.value: 3,
    Status.UNKNOWN.value: 4,
    Status.RELEASED.value: 5,
}


def promised_days(paper: Paper, venue: VenueConfig, today: date) -> int:
    """承诺天数：从论文首次公开和会议开幕中较晚的那天算起。"""
    start = max(date.fromisoformat(paper.published), date.fromisoformat(venue.conference_date))
    return max((today - start).days, 0)


def _repo_row(
    paper: Paper,
    link: RepoLink,
    snap: RepoSnapshot,
    venue: VenueConfig,
    cfg: ClassifyConfig,
    today: date,
) -> dict[str, Any]:
    verdict = classify(snap, cfg)
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "url": paper.url,
        "repo": link.repo,
        "status": verdict.status.value,
        "promise_text": verdict.promise_text,
        "paper_sentence": link.sentence,
        "future": link.future,
        "where": link.where,
        "promised_days": promised_days(paper, venue, today),
        "last_commit": snap.last_commit[:10],
        "file_count": snap.file_count,
        "listing": [list(x) for x in snap.listing],
        "checked_at": snap.checked_at[:10],
    }


def _no_repo_row(paper: Paper, kind: str, evidence: str, venue: VenueConfig, today: date):
    return {
        "paper_id": paper.paper_id,
        "title": paper.title,
        "url": paper.url,
        "kind": kind,  # anonymous（定稿仍是匿名链接）或 no_link（说了会发布但没给链接）
        "evidence": evidence,
        "promised_days": promised_days(paper, venue, today),
    }


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(r["status"] for r in rows)
    return {s.value: counts.get(s.value, 0) for s in Status}


def build_venue(
    venue: VenueConfig,
    papers: list[Paper],
    links: list[RepoLink],
    snapshots: list[RepoSnapshot],
    cfg: ClassifyConfig,
    today: date,
    fulltexts: dict[str, FullText] | None = None,
) -> dict[str, Any]:
    fulltexts = fulltexts or {}
    by_paper = {link.paper_id: link for link in links}
    by_repo = {s.repo.lower(): s for s in snapshots}
    rows, no_repo = [], []
    for paper in papers:
        link = by_paper.get(paper.paper_id)
        if link is not None:
            snap = by_repo.get(link.repo.lower())
            if snap is not None:
                rows.append(_repo_row(paper, link, snap, venue, cfg, today))
            continue
        full = fulltexts.get(paper.paper_id)
        if anon := anonymous_link(full):
            no_repo.append(_no_repo_row(paper, "anonymous", anon, venue, today))
        elif sentence := promise_without_link(full):
            no_repo.append(_no_repo_row(paper, "no_link", sentence, venue, today))

    rows.sort(key=lambda r: (_STATUS_ORDER[r["status"]], -r["promised_days"]))
    no_repo.sort(key=lambda r: (r["kind"], -r["promised_days"]))
    return {
        "venue": venue.key,
        "name": venue.name,
        "built_on": today.isoformat(),
        "papers": len(papers),
        "papers_with_fulltext": sum(1 for f in fulltexts.values() if f.available),
        "papers_with_repo": len(by_paper),
        "checked": len(rows),
        "counts": status_counts(rows),
        "counts_future": status_counts([r for r in rows if r["future"]]),
        "no_repo_counts": dict(Counter(r["kind"] for r in no_repo)),
        "rows": rows,
        "no_repo": no_repo,
    }
