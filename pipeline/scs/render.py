"""把 build 生成的数据渲染成静态网站。

模板、样式、文案都在 web/ 目录里，这里只负责组装页面。输出：
    public/index.html            最新一年的年份页（英文）
    public/<year>.html           某一年：逐年对比表 + 这一年各会议的方格图
    public/<venue>.html          一个会议的完整列表
    public/about.html            判定规则
    public/zh/…                  中文版，结构相同
    public/static/               样式、脚本、字体
"""

from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any

from scs.render_index import (
    Upcoming,
    default_year,
    not_delivered,
    other_years,
    with_repo,
    year_content,
    year_page,
    years_of,
)
from scs.render_parts import all_rows, counts_of, entry_groups, legend, waffle

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
LANGS = ("en", "zh")


def _fill(template: str, **values: str) -> str:
    """替换 {{name}}。值必须已经转义过。"""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


# ---------- 页面内容 ----------


def venue_content(
    site: dict[str, Any],
    t: dict[str, Any],
    promise: re.Pattern[str],
    sites: list[dict[str, Any]] = (),
) -> str:
    """sites：所有会议，用来链接同一会议的其他年份。"""
    rows = all_rows(site)
    repo_rows = with_repo(rows)
    n, total = not_delivered(repo_rows), len(repo_rows)
    hero = t["hero_venue"].format(n=n, total=f"{total:,}", venue=site["name"])
    toggle = (
        f'<button type="button" class="expand" data-expand="{escape(t["expand_all"])}" '
        f'data-collapse="{escape(t["collapse_all"])}">{escape(t["expand_all"])}</button>'
    )
    return (
        f"{other_years(site, list(sites) or [site], t)}"
        f'<section class="hero"><h1>{escape(hero)}</h1><p>{escape(t["lede_venue"])}</p></section>'
        f"{waffle(repo_rows, t)}{legend(counts_of(rows), t, site.get('checklist_open', 0))}"
        f'<div class="list-head"><p class="count" data-template="{escape(t["count"])}">'
        f"{escape(t['count'].format(n=len(rows)))}</p>"
        f'<div class="tools">{toggle}<input class="search" type="search" '
        f'placeholder="{escape(t["search"])}" aria-label="{escape(t["search"])}"></div></div>'
        f"{entry_groups(rows, t, promise)}"
        f'<p class="nothing" hidden>{escape(t["nothing"])}</p>'
    )


def about_content(lang: str) -> str:
    return (WEB_DIR / "templates" / f"about.{lang}.html").read_text(encoding="utf-8")


# ---------- 页面外壳 ----------


def _page(
    lang: str,
    name: str,
    title: str,
    content: str,
    strings: dict,
    checked: str,
    repo_url: str,
    scripts: str = "",
) -> str:
    t = strings[lang]
    other = "zh" if lang == "en" else "en"
    link = (
        f'<a href="{escape(repo_url)}/issues">{escape(t["correction_link"])}</a>'
        if repo_url
        else escape(t["correction_link"])
    )
    current = ' aria-current="page"'
    return _fill(
        (WEB_DIR / "templates" / "base.html").read_text(encoding="utf-8"),
        lang="zh-CN" if lang == "zh" else "en",
        title=escape(title),
        description=escape(t["description"]),
        root="" if lang == "en" else "../",
        nav_index=escape(t["nav_index"]),
        nav_about=escape(t["nav_about"]),
        current_index=current if name == "index.html" or re.fullmatch(r"\d{4}\.html", name) else "",
        current_about=current if name == "about.html" else "",
        other_lang="zh-CN" if other == "zh" else "en",
        other_lang_url=("zh/" if other == "zh" else "../") + name,
        other_lang_name=escape(strings[other]["lang_name"]),
        content=content,
        footer_data=escape(t["footer_data"].format(date=checked)),
        footer_correction=t["footer_correction"].format(link=link),
        scripts=scripts,
    )


def render_site(
    sites: list[dict[str, Any]],
    out_dir: Path,
    repo_url: str = "",
    promise: re.Pattern[str] | None = None,
    upcoming: list[Upcoming] = (),
    wait_days: int = 0,
) -> list[Path]:
    """sites：各会议 build 生成的数据。promise：README 里承诺短语的正则，用来做荧光笔标记。

    upcoming：已配置但还没到展示时间的会议，在对应年份里列出上线日期。
    """
    upcoming = list(upcoming)
    years = years_of(sites, upcoming)
    home = default_year(sites, upcoming)
    promise = promise or re.compile(r"coming soon|will be \w+", re.IGNORECASE)
    strings = json.loads((WEB_DIR / "i18n.json").read_text(encoding="utf-8"))
    checked = max(
        (r["checked_at"] for s in sites for r in s["rows"]),
        default=max(s["built_on"] for s in sites),
    )
    written = []
    for lang in LANGS:
        t = strings[lang]
        folder = out_dir if lang == "en" else out_dir / lang
        folder.mkdir(parents=True, exist_ok=True)
        root = "" if lang == "en" else "../"
        script = f'<script src="{root}static/app.js"></script>'
        pages = [
            ("index.html", t["title_index"], year_content(home, sites, upcoming, t, wait_days), "")
        ]
        pages += [
            (
                year_page(y),
                t["title_year"].format(year=y),
                year_content(y, sites, upcoming, t, wait_days),
                "",
            )
            for y in years
        ]
        pages += [
            (
                f"{s['venue']}.html",
                t["title_venue"].format(venue=s["name"]),
                venue_content(s, t, promise, sites),
                script,
            )
            for s in sites
        ]
        pages.append(("about.html", t["title_about"], about_content(lang), ""))
        for name, title, content, scripts in pages:
            path = folder / name
            path.write_text(
                _page(lang, name, title, content, strings, checked, repo_url, scripts),
                encoding="utf-8",
            )
            written.append(path)
    shutil.copytree(WEB_DIR / "static", out_dir / "static", dirs_exist_ok=True)
    return written
