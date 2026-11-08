"""数据文件读写。所有数据都是 JSONL：一行一条记录，方便看 git diff。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from scs.models import Fragment, FullText, Paper, RepoLink, RepoSnapshot

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def path_for(stage: str, venue: str, data_dir: Path = DATA_DIR) -> Path:
    """stage 是 papers / fulltext / links / snapshots 之一。"""
    return data_dir / stage / f"{venue}.jsonl"


def write_jsonl(path: Path, records: Iterable[Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            obj = asdict(r) if is_dataclass(r) else r
            f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------- 按类型读取各步骤的数据 ----------


def load_papers(venue: str, data_dir: Path = DATA_DIR) -> list[Paper]:
    return [Paper(**r) for r in read_jsonl(path_for("papers", venue, data_dir))]


def load_links(venue: str, data_dir: Path = DATA_DIR) -> list[RepoLink]:
    return [
        RepoLink(**{**r, "all_repos": tuple(r["all_repos"])})
        for r in read_jsonl(path_for("links", venue, data_dir))
    ]


# 快照里大多数仓库都为空的字段，为空时不写，省空间
_OPTIONAL = ("tasks", "present_kinds")


def save_snapshots(venue: str, snapshots: list[RepoSnapshot], data_dir: Path = DATA_DIR) -> None:
    """检查时间不写进每一行，单独存一个文件。

    这样仓库没变化时快照文件也不变，每天的提交里只出现真正有变化的仓库。
    """
    path = path_for("snapshots", venue, data_dir)
    rows = (
        {k: v for k, v in asdict(s).items() if k != "checked_at" and (v or k not in _OPTIONAL)}
        for s in snapshots
    )
    write_jsonl(path, rows)
    checked = max((s.checked_at for s in snapshots), default="")
    path.with_suffix(".checked").write_text(checked + "\n", encoding="utf-8")


def load_snapshots(venue: str, data_dir: Path = DATA_DIR) -> list[RepoSnapshot]:
    path = path_for("snapshots", venue, data_dir)
    stamp = path.with_suffix(".checked")
    checked = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
    return [
        RepoSnapshot(
            **{
                "checked_at": checked,
                **r,
                "listing": tuple(tuple(x) for x in r.get("listing", ())),
                "tasks": tuple(tuple(x) for x in r.get("tasks", ())),
                "present_kinds": tuple(r.get("present_kinds", ())),
            }
        )
        for r in read_jsonl(path)
    ]


def load_fulltexts(venue: str, data_dir: Path = DATA_DIR) -> dict[str, FullText]:
    """没有正文数据时返回空字典。"""
    path = path_for("fulltext", venue, data_dir)
    if not path.exists():
        return {}
    out = {}
    for r in read_jsonl(path):
        frags = tuple(
            Fragment(f["kind"], f["section"], tuple(f["hrefs"]), f["text"]) for f in r["fragments"]
        )
        out[r["paper_id"]] = FullText(r["paper_id"], r["http_status"], frags)
    return out
