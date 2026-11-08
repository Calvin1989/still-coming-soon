"""命令行入口。每个子命令对应一步，读上一步的文件，写这一步的文件。

python -m scs papers   --venue iclr2025 [--dump data/raw/iclr2025-arxiv.json]
python -m scs fulltext --venue iclr2025 [--dump data/raw/iclr2025-fulltext.json] [--limit N]
python -m scs links    --venue iclr2025
python -m scs probe    --venue iclr2025 [--limit N]
python -m scs build    --venue iclr2025
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from scs import config, store
from scs.build import build_venue
from scs.links import resolve
from scs.probe import probe_many
from scs.render import render_site
from scs.sources import arxiv_html
from scs.sources.arxiv import ArxivSource


def cmd_papers(args: argparse.Namespace, cfg: config.Config) -> None:
    venue = cfg.venues[args.venue]
    papers = ArxivSource(venue, dump=args.dump).fetch()
    n = store.write_jsonl(store.path_for("papers", venue.key), papers)
    print(f"papers: {n} 篇录用论文")


def cmd_fulltext(args: argparse.Namespace, cfg: config.Config) -> None:
    known = {p.paper_id for p in store.load_papers(args.venue)}
    if args.dump:
        fulltexts = [f for f in arxiv_html.load_dump(args.dump) if f.paper_id in known]
    else:
        fulltexts = arxiv_html.fetch_many(sorted(known)[: args.limit])
    store.write_jsonl(store.path_for("fulltext", args.venue), fulltexts)
    statuses = Counter(f.http_status for f in fulltexts)
    print(f"fulltext: {len(fulltexts)} 篇，HTTP 状态 {dict(statuses)}")


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
    store.save_snapshots(args.venue, snapshots)
    errors = sum(1 for s in snapshots if s.error)
    print(f"probe: 检查了 {len(snapshots)} 个仓库，其中 {errors} 个检查失败")


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


def cmd_render(args: argparse.Namespace, cfg: config.Config) -> None:
    """渲染所有已生成数据的会议（按 config.toml 里的顺序），--venue 参数不影响范围。"""
    sites = []
    for key in cfg.venues:
        site_file = store.DATA_DIR / "site" / f"{key}.json"
        if site_file.exists():
            sites.append(json.loads(site_file.read_text(encoding="utf-8")))
    promise = re.compile("|".join(p.pattern for p in cfg.classify.promise_phrases), re.IGNORECASE)
    pages = render_site(sites, args.out, cfg.repo_url, promise)
    print(f"render: {len(sites)} 个会议，生成了 {len(pages)} 个页面，输出到 {args.out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scs")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("papers", "fulltext", "links", "probe", "build", "render"):
        p = sub.add_parser(name)
        p.add_argument("--venue", required=name != "render")
        if name in ("papers", "fulltext"):
            p.add_argument("--dump", type=Path, help="读取已保存的原始数据，不联网")
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
    }
    commands[args.command](args, cfg)
