"""命令行入口。每个子命令对应一步，读上一步的文件，写这一步的文件。

python -m scs papers   --venue iclr2025 [--dump data/raw/iclr2025-arxiv.json]
python -m scs fulltext --venue iclr2025 [--dump data/raw/iclr2025-fulltext.json] [--limit N]
python -m scs links    --venue iclr2025
python -m scs probe    --venue iclr2025 [--limit N]
python -m scs build    --venue iclr2025
python -m scs render
python -m scs venues   [--when held|due] [--with-data] [--json]   给 GitHub Actions 用
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from datetime import date
from pathlib import Path

from scs import config, schedule, store
from scs.build import build_venue
from scs.links import fallback_repos, resolve
from scs.probe import probe_many
from scs.render import render_site
from scs.render_index import Upcoming
from scs.sources import arxiv_html, ccfddl
from scs.sources.arxiv import ArxivSource


def cmd_papers(args: argparse.Namespace, cfg: config.Config) -> None:
    venue = cfg.venues[args.venue]
    papers = ArxivSource(venue, dump=args.dump).fetch()
    n = store.write_jsonl(store.path_for("papers", venue.key), papers)
    print(f"papers: {n} 篇录用论文")


def cmd_fulltext(args: argparse.Namespace, cfg: config.Config) -> None:
    """只处理还没有正文的论文，已有的保留（第一次全量很慢，之后每次只抓新论文）。

    --minutes：最多抓这么久，每抓一批就保存一次；没抓完的下次接着抓。
    """
    known = {p.paper_id for p in store.load_papers(args.venue)}
    merged = store.load_fulltexts(args.venue)
    if args.dump:
        _save_fulltexts(args.venue, merged, arxiv_html.load_dump(args.dump), known)
        return
    todo = arxiv_html.missing(sorted(known), merged)[: args.limit]
    print(f"fulltext: 需要抓取 {len(todo)} 篇（已有 {len(merged)} 篇）")
    deadline = time.monotonic() + args.minutes * 60 if args.minutes else None
    for start in range(0, len(todo), FULLTEXT_BATCH):
        batch = arxiv_html.fetch_many(todo[start : start + FULLTEXT_BATCH], deadline)
        _save_fulltexts(args.venue, merged, batch, known)
        if len(batch) < len(todo[start : start + FULLTEXT_BATCH]):
            print(f"fulltext: 到了 {args.minutes} 分钟的上限，剩下的下次再抓")
            break


FULLTEXT_BATCH = 200


def _save_fulltexts(venue: str, merged: dict, new: list, known: set[str]) -> None:
    merged.update({f.paper_id: f for f in new if f.paper_id in known})
    fulltexts = [merged[pid] for pid in sorted(merged) if pid in known]
    store.write_jsonl(store.path_for("fulltext", venue), fulltexts)
    statuses = Counter(f.http_status for f in fulltexts)
    print(f"fulltext: 共 {len(fulltexts)} 篇，HTTP 状态 {dict(statuses)}")


def cmd_links(args: argparse.Namespace, cfg: config.Config) -> None:
    papers = store.load_papers(args.venue)
    fulltexts = store.load_fulltexts(args.venue)
    links = [link for p in papers if (link := resolve(p, fulltexts.get(p.paper_id)))]
    store.write_jsonl(store.path_for("links", args.venue), links)
    where = Counter(link.where for link in links)
    print(f"links: {len(papers)} 篇论文中 {len(links)} 篇有自己的仓库链接，位置 {dict(where)}")


def cmd_probe(args: argparse.Namespace, cfg: config.Config) -> None:
    links = store.load_links(args.venue)
    repos = list(dict.fromkeys(link.repo for link in links))[: args.limit]
    snapshots = probe_many(repos, cfg.probe)
    # 不存在的仓库：再试同一篇论文里的其他写法（见 links.fallback_repos）
    gone = {s.repo.lower() for s in snapshots if s.gone}
    checked = {s.repo.lower() for s in snapshots}
    extra = [
        r
        for link in links
        if link.repo.lower() in gone
        for r in fallback_repos(link)
        if r.lower() not in checked
    ]
    snapshots += probe_many(list(dict.fromkeys(extra)), cfg.probe)
    store.save_snapshots(args.venue, snapshots)
    errors = sum(1 for s in snapshots if s.error)
    print(
        f"probe: 检查了 {len(snapshots)} 个仓库（其中 {len(set(extra))} 个是备选写法），"
        f"{errors} 个检查失败"
    )


def cmd_build(args: argparse.Namespace, cfg: config.Config) -> None:
    venue = cfg.venues[args.venue]
    site = build_venue(
        venue,
        store.load_papers(venue.key),
        store.load_links(venue.key),
        store.load_snapshots(venue.key),
        cfg.classify,
        date.today(),
        store.load_fulltexts(venue.key),
    )
    out = store.DATA_DIR / "site" / f"{venue.key}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(site, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"build: {site['checked']} 个仓库，状态分布 {site['counts']}")
    print(
        f"       写了'将会发布'的 {sum(site['counts_future'].values())} 个：{site['counts_future']}"
    )
    print(f"       没有仓库但有承诺：{site['no_repo_counts']}")


def cmd_schedule(args: argparse.Namespace, cfg: config.Config) -> None:
    """从 ccfddl 发现新公布日期的会议，写到 data/schedule.json。"""
    manual = {k: v for k, v in cfg.venues.items() if k not in cfg.auto_keys}
    found, failed = schedule.discover(cfg.auto_series, manual, ccfddl.fetch)
    path = config.DEFAULT_SCHEDULE
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged = schedule.merge(old, found, failed)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for key in sorted(set(merged) - set(old)):
        entry = merged[key]
        print(f"schedule: 新公布 {key}，开幕 {entry['conference_date']}（{entry['said']}）")
    if failed:
        print(f"schedule: 读取失败，保留原来的记录：{', '.join(failed)}")
    print(f"schedule: 自动加入的会议共 {len(merged)} 个")


def cmd_venues(args: argparse.Namespace, cfg: config.Config) -> None:
    """列出该处理的会议。

    held：已开幕，每月抓论文。due：开幕满 wait_days 天，每天检查仓库、上网站。
    """
    today = date.today()
    keys = cfg.held_venues(today) if args.when == "held" else cfg.due_venues(today)
    if args.with_data:
        keys = [k for k in keys if store.path_for("papers", k).exists()]
    print(json.dumps(keys) if args.json else " ".join(keys))


def cmd_render(args: argparse.Namespace, cfg: config.Config) -> None:
    """渲染已到展示时间、且已生成数据的会议（按 config.toml 里的顺序）。"""
    sites = []
    for key in cfg.due_venues(date.today()):
        site_file = store.DATA_DIR / "site" / f"{key}.json"
        if site_file.exists():
            sites.append(json.loads(site_file.read_text(encoding="utf-8")))
    promise = re.compile("|".join(p.pattern for p in cfg.classify.promise_phrases), re.IGNORECASE)
    today = date.today()
    upcoming = [
        Upcoming(v.key, v.name, v.year, v.shown_from(cfg.wait_days).isoformat())
        for v in cfg.venues.values()
        if not v.due(today, cfg.wait_days)
    ]
    pages = render_site(sites, args.out, cfg.repo_url, promise, upcoming, cfg.wait_days)
    print(f"render: {len(sites)} 个会议，生成了 {len(pages)} 个页面，输出到 {args.out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("schedule")
    for name in ("papers", "fulltext", "links", "probe", "build", "render", "venues"):
        p = sub.add_parser(name)
        if name == "venues":
            p.add_argument("--when", choices=("held", "due"), default="due")
            p.add_argument("--with-data", action="store_true", help="只要已经抓过论文的")
            p.add_argument("--json", action="store_true")
            continue
        p.add_argument("--venue", required=name != "render")
        if name in ("papers", "fulltext"):
            p.add_argument("--dump", type=Path, help="读取已保存的原始数据，不联网")
        if name == "fulltext":
            p.add_argument("--minutes", type=float, default=None, help="最多抓多久（分钟）")
        if name in ("fulltext", "probe"):
            p.add_argument("--limit", type=int, default=None, help="只处理前 N 个（调试用）")
        if name == "render":
            p.add_argument("--out", type=Path, default=store.DATA_DIR.parent / "public")
    args = parser.parse_args(argv)
    cfg = config.load()
    commands = {
        "papers": cmd_papers,
        "fulltext": cmd_fulltext,
        "links": cmd_links,
        "probe": cmd_probe,
        "build": cmd_build,
        "render": cmd_render,
        "venues": cmd_venues,
        "schedule": cmd_schedule,
    }
    commands[args.command](args, cfg)
