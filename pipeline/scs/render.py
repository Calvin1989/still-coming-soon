"""把 build 生成的数据渲染成静态网站。

模板、样式、文案都在 web/ 目录里，这里只负责组装页面。输出：
    public/index.html            各会议对比（英文）
    public/<venue>.html          一个会议的完整列表
    public/about.html            判定规则
    public/zh/…                  中文版，结构相同
    public/static/               样式、脚本、字体
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path
from typing import Any

from scs.render_parts import UNDELIVERED, all_rows, counts_of, entry, legend, waffle

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
LANGS = ("en", "zh")


def _fill(template: str, **values: str) -> str:
    """替换 {{name}}。值必须已经转义过。"""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


def _pct(n: int, total: int) -> str:
    return f"{n / total:.1%}" if total else "–"


def _not_delivered(rows: list[dict[str, Any]]) -> int:
    counts = counts_of(rows)
    return sum(counts.get(s, 0) for s in UNDELIVERED)


def _with_repo(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("repo")]


# ---------- 页面内容 ----------


def _year(site: dict[str, Any]) -> str:
    """会议年份。旧数据没有 conference_date 时从名字里取。"""
    if site.get("conference_date"):
        return site["conference_date"][:4]
    found = re.search(r"20\d\d", site["name"])
    return found.group(0) if found else ""


def _days_since(site: dict[str, Any]) -> int | None:
    if not site.get("conference_date"):
        return None
    return (date.fromisoformat(site["built_on"]) - date.fromisoformat(site["conference_date"])).days


def _rate(site: dict[str, Any]) -> float:
    rows = _with_repo(all_rows(site))
    return _not_delivered(rows) / len(rows) if rows else 0.0


def _by_year(sites: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """按年份分组，新的在前；同一年里按未兑现比例从低到高。"""
    years: dict[str, list[dict[str, Any]]] = {}
    for site in sites:
        years.setdefault(_year(site), []).append(site)
    return [(y, sorted(years[y], key=_rate)) for y in sorted(years, reverse=True)]


def _hero_index(sites: list[dict[str, Any]], t: dict[str, Any]) -> str:
    """标题比较同一年里兑现率最高和最低的会议（不同年份的会议过去的时间不同，不放在一起比）。

    用有两个会议以上的最近一年；都只有一个会议时，用通用标题。
    """
    for _, group in _by_year(sites):
        rated = [(_rate(s), s["name"]) for s in group if _with_repo(all_rows(s))]
        if len(rated) >= 2:
            low, high = min(rated), max(rated)
            return t["hero_compare"].format(
                low=low[1], low_pct=f"{low[0]:.1%}", high=high[1], high_pct=f"{high[0]:.1%}"
            )
    return t["hero_index"]


def _venue_block(site: dict[str, Any], t: dict[str, Any]) -> str:
    rows = _with_repo(all_rows(site))
    n, total = _not_delivered(rows), len(rows)
    page = f"{site['venue']}.html"
    days = _days_since(site)
    age = f'<p class="age">{escape(t["venue_age"].format(d=days))}</p>' if days is not None else ""
    return (
        f'<li class="venue"><div><h3><a href="{page}">{escape(site["name"])}</a></h3>'
        f'<p class="rate">{t["venue_rate"].format(pct=_pct(n, total), n=n, total=f"{total:,}")}'
        f"</p>{age}</div><div>{waffle(rows, t, href_prefix=page)}"
        f'<p class="open"><a href="{page}">{escape(t["venue_open"].format(n=n))}</a></p>'
        f"</div></li>"
    )


def _upcoming_note(items: list[tuple[str, str]], t: dict[str, Any], wait_days: int) -> str:
    """还没到展示时间的会议：名字和上线日期。"""
    if not items:
        return ""
    names = t["upcoming_sep"].join(
        t["upcoming_item"].format(name=escape(name), date=day) for name, day in items
    )
    text = escape(t["upcoming"]).format(wait=wait_days, items=names)
    return f'<p class="upcoming">{text}</p>'


def index_content(
    sites: list[dict[str, Any]],
    t: dict[str, Any],
    upcoming: list[tuple[str, str, str]] = (),
    wait_days: int = 0,
) -> str:
    """upcoming：(年份, 会议名, 上线日期)，还没到展示时间的会议。"""
    groups = dict(_by_year(sites))
    for year, _, _ in upcoming:
        groups.setdefault(year, [])
    years = sorted(groups, reverse=True)
    jump = ""
    if len(years) > 1:
        links = " ".join(f'<a href="#y{y}">{y}</a>' for y in years)
        jump = f'<p class="jump">{escape(t["jump"])} {links}</p>'
    sections = []
    for year in years:
        group = sorted(groups[year], key=_rate)
        ages = [d for s in group if (d := _days_since(s)) is not None]
        note = (
            t["year_note"].format(n=len(group), low=min(ages), high=max(ages))
            if ages and len(group) > 1
            else ""
        )
        later = [(name, day) for y, name, day in upcoming if y == year]
        blocks = "".join(_venue_block(s, t) for s in group)
        sections.append(
            f'<section class="year" id="y{year}"><header class="year-head"><h2>{year}</h2>'
            f"<p>{escape(note)}</p></header>"
            + (f'<ul class="venues">{blocks}</ul>' if blocks else "")
            + f"{_upcoming_note(later, t, wait_days)}</section>"
        )
    return (
        f'<section class="hero"><h1>{escape(_hero_index(sites, t))}</h1>'
        f"<p>{escape(t['lede_index'])}</p>{jump}</section>" + "".join(sections)
    )


def venue_content(site: dict[str, Any], t: dict[str, Any], promise: re.Pattern[str]) -> str:
    rows = all_rows(site)
    repo_rows = _with_repo(rows)
    n, total = _not_delivered(repo_rows), len(repo_rows)
    hero = t["hero_venue"].format(n=n, total=f"{total:,}", venue=site["name"])
    items = "\n".join(entry(r, t, promise) for r in rows)
    return (
        f'<section class="hero"><h1>{escape(hero)}</h1><p>{escape(t["lede_venue"])}</p></section>'
        f"{waffle(repo_rows, t)}{legend(counts_of(rows), t)}"
        f'<div class="list-head"><p class="count" data-template="{escape(t["count"])}">'
        f"{escape(t['count'].format(n=len(rows)))}</p>"
        f'<input class="search" type="search" placeholder="{escape(t["search"])}" '
        f'aria-label="{escape(t["search"])}"></div>'
        f'<ul class="entries">\n{items}\n</ul>'
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
        current_index=current if name == "index.html" else "",
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
    upcoming: list[tuple[str, str, str]] = (),
    wait_days: int = 0,
) -> list[Path]:
    """sites：各会议 build 生成的数据。promise：README 里承诺短语的正则，用来做荧光笔标记。

    upcoming：(年份, 会议名, 上线日期)，已配置但还没到展示时间的会议，首页上提一句。
    """
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
        index = index_content(sites, t, upcoming, wait_days)
        pages = [("index.html", t["title_index"], index, "")]
        pages += [
            (
                f"{s['venue']}.html",
                t["title_venue"].format(venue=s["name"]),
                venue_content(s, t, promise),
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
