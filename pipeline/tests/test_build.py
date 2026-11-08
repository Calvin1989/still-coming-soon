from datetime import date

from scs import config
from scs.build import build_venue
from scs.models import Paper, RepoLink, RepoSnapshot

CFG = config.load()


def snap(repo, exists=True, code=0):
    return RepoSnapshot(
        repo, "2026-11-08T00:00:00", exists, ext_bytes={".py": code} if code else {}
    )


def test_gone_repository_falls_back_to_another_spelling_in_the_paper():
    paper = Paper("arxiv:1", "iclr2025", "T", "u", "2025-01-01", "")
    links = [RepoLink("arxiv:1", "fkluger/parsacare", ("fkluger/parsacare", "fkluger/parsac"))]
    snaps = [snap("fkluger/parsacare", exists=False), snap("fkluger/parsac", code=50_000)]
    site = build_venue(
        CFG.venues["iclr2025"], [paper], links, snaps, CFG.classify, date(2026, 11, 8)
    )
    row = site["rows"][0]
    assert (row["status"], row["repo"], row["linked_repo"]) == (
        "released",
        "fkluger/parsac",
        "fkluger/parsacare",
    )
    # 备选也不存在时仍然是 gone
    snaps = [snap("fkluger/parsacare", exists=False), snap("fkluger/parsac", exists=False)]
    site = build_venue(
        CFG.venues["iclr2025"], [paper], links, snaps, CFG.classify, date(2026, 11, 8)
    )
    assert site["rows"][0]["status"] == "gone" and site["rows"][0]["linked_repo"] == ""
