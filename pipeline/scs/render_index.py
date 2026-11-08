"""首页和年份页。

每个年份页（首页就是最新一年的年份页）从上到下：
    标题：这一年里兑现率最好和最差的会议
    逐年对比表：一行一个会议系列，一列一年，所有年份页都一样
    年份标签：切换到其他年份
    这一年各会议的方格图，以及还没到展示时间的会议
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape
from typing import Any

from scs.render_parts import UNDELIVERED, all_rows, counts_of, waffle

BAR_PX = 72  # 对比表里最高的比例画多长


@dataclass(frozen=True)
class Upcoming:
    """已配置但还没到展示时间的会议。"""

    venue: str
    name: str
    year: str
    shown_from: str  # 上线日期，YYYY-MM-DD


# ---------- 数据 ----------


def with_repo(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r.get("repo")]


def not_delivered(rows: list[dict[str, Any]]) -> int:
    counts = counts_of(rows)
    return sum(counts.get(s, 0) for s in UNDELIVERED)


def rate(site: dict[str, Any]) -> float:
    rows = with_repo(all_rows(site))
    return not_delivered(rows) / len(rows) if rows else 0.0


def year_of(site: dict[str, Any]) -> str:
    """会议年份。旧数据没有 conference_date 时从名字里取。"""
    if site.get("conference_date"):
        return site["conference_date"][:4]
    found = re.search(r"20\d\d", site["name"])
    return found.group(0) if found else ""


def days_since(site: dict[str, Any]) -> int | None:
    if not site.get("conference_date"):
        return None
    held = date.fromisoformat(site["conference_date"])
    return (date.fromisoformat(site["built_on"]) - held).days


def series_of(venue_key: str) -> str:
    """同一个会议不同年份的共同部分：iclr2025 → iclr。"""
    return re.sub(r"\d{4}$", "", venue_key)


def series_name(name: str) -> str:
    return re.sub(r"\s*\d{4}$", "", name)


def years_of(sites: list[dict[str, Any]], upcoming: list[Upcoming]) -> list[str]:
    """网站上显示的年份，新的在前：有结果的年份。

    还没有任何结果的年份不单独显示，它的会议列在最新一年的"暂不展示"里。
    """
    with_data = {year_of(s) for s in sites}
    return sorted(with_data or {u.year for u in upcoming}, reverse=True)


def default_year(sites: list[dict[str, Any]], upcoming: list[Upcoming]) -> str:
    """首页显示有数据的最新一年；都没数据时显示最新的年份。"""
    with_data = sorted({year_of(s) for s in sites}, reverse=True)
    return with_data[0] if with_data else years_of(sites, upcoming)[0]


def year_page(year: str) -> str:
    return f"{year}.html"


def _age_range(sites: list[dict[str, Any]]) -> tuple[int, int] | None:
    ages = [d for s in sites if (d := days_since(s)) is not None]
    return (min(ages), max(ages)) if ages else None


def _pct(n: int, total: int) -> str:
    return f"{n / total:.1%}" if total else "–"


# ---------- 各部分 ----------


def hero(sites: list[dict[str, Any]], t: dict[str, Any]) -> str:
    """比较同一年里兑现率最高和最低的会议；不足两个会议时用通用标题。"""
    rated = [(rate(s), s["name"]) for s in sites if with_repo(all_rows(s))]
    if len(rated) < 2:
        return t["hero_index"]
    low, high = min(rated), max(rated)
    return t["hero_compare"].format(
        low=low[1], low_pct=f"{low[0]:.1%}", high=high[1], high_pct=f"{high[0]:.1%}"
    )


def _short_date(day: str, t: dict[str, Any]) -> str:
    d = date.fromisoformat(day)
    months = t.get("months") or [""] * 12  # 中文直接用数字月份
    return t["soon_cell"].format(mon=months[d.month - 1], m=d.month, d=d.day)


def trend_table(sites: list[dict[str, Any]], upcoming: list[Upcoming], t: dict[str, Any]) -> str:
    """逐年对比表。行按各年平均未兑现比例从低到高。"""
    years = sorted(years_of(sites, upcoming))
    cells: dict[tuple[str, str], str] = {}
    names: dict[str, str] = {}
    rates: dict[str, list[float]] = {}
    top = max((rate(s) for s in sites), default=0) or 1
    for s in sites:
        key, y = series_of(s["venue"]), year_of(s)
        names[key] = series_name(s["name"])
        rows = with_repo(all_rows(s))
        n, total = not_delivered(rows), len(rows)
        rates.setdefault(key, []).append(rate(s))
        title = escape(t["cell_title"].format(name=s["name"], n=n, total=f"{total:,}"))
        cells[key, y] = (
            f'<td><a href="{s["venue"]}.html" title="{title}">'
            f'<span class="pct">{_pct(n, total)}</span>'
            f'<span class="bar" style="width:{round(rate(s) / top * BAR_PX)}px"></span></a></td>'
        )
    for u in upcoming:
        if u.year not in years:
            continue
        key = series_of(u.venue)
        names.setdefault(key, series_name(u.name))
        cells[key, u.year] = f'<td class="soon">{escape(_short_date(u.shown_from, t))}</td>'

    def order(key: str) -> tuple[bool, float]:
        r = rates.get(key)
        return (r is None, sum(r) / len(r) if r else 0.0)

    head = "".join(
        f'<th scope="col"><a href="{year_page(y)}#years">{y}</a>{_age_note(y, sites, t)}</th>'
        for y in years
    )
    body = "".join(
        f'<tr><th scope="row">{escape(names[k])}</th>'
        + "".join(cells.get((k, y), '<td class="none">–</td>') for y in years)
        + "</tr>"
        for k in sorted(names, key=order)
    )
    return (
        f'<section class="trend"><h2>{escape(t["trend_title"])}</h2>'
        f'<p class="note">{escape(t["trend_note"])}</p>'
        f'<div class="trend-scroll"><table><thead><tr><th scope="col">'
        f'<span class="sr-only">{escape(t["trend_series"])}</span></th>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div></section>"
    )


def _age_note(year: str, sites: list[dict[str, Any]], t: dict[str, Any]) -> str:
    ages = _age_range([s for s in sites if year_of(s) == year])
    if not ages:
        return ""
    low, high = ages
    text = t["age_one"].format(d=low) if low == high else t["age_range"].format(low=low, high=high)
    return f"<small>{escape(text)}</small>"


def year_tabs(years: list[str], current: str, t: dict[str, Any]) -> str:
    current_attr = ' aria-current="page"'
    links = "".join(
        f'<a href="{year_page(y)}#years"{current_attr if y == current else ""}>{y}</a>'
        for y in sorted(years)
    )
    return f'<nav class="years" id="years" aria-label="{escape(t["years_label"])}">{links}</nav>'


def _venue_block(site: dict[str, Any], t: dict[str, Any]) -> str:
    rows = with_repo(all_rows(site))
    n, total = not_delivered(rows), len(rows)
    page = f"{site['venue']}.html"
    days = days_since(site)
    age = f'<p class="age">{escape(t["venue_age"].format(d=days))}</p>' if days is not None else ""
    return (
        f'<li class="venue"><div><h3><a href="{page}">{escape(site["name"])}</a></h3>'
        f'<p class="rate">{t["venue_rate"].format(pct=_pct(n, total), n=n, total=f"{total:,}")}'
        f"</p>{age}</div><div>{waffle(rows, t, href_prefix=page)}"
        f'<p class="open"><a href="{page}">{escape(t["venue_open"].format(n=n))}</a></p>'
        f"</div></li>"
    )


def _upcoming_note(items: list[Upcoming], t: dict[str, Any], wait_days: int) -> str:
    if not items:
        return ""
    names = t["upcoming_sep"].join(
        t["upcoming_item"].format(name=escape(u.name), date=u.shown_from) for u in items
    )
    return f'<p class="upcoming">{escape(t["upcoming"]).format(wait=wait_days, items=names)}</p>'


def year_content(
    year: str,
    sites: list[dict[str, Any]],
    upcoming: list[Upcoming],
    t: dict[str, Any],
    wait_days: int,
) -> str:
    """一个年份页的完整内容。sites、upcoming 是所有年份的，用于对比表和标签。"""
    group = sorted((s for s in sites if year_of(s) == year), key=rate)
    shown = years_of(sites, upcoming)
    # 这一年还没上线的会议；最新一年还要加上那些还没有任何结果的年份的会议
    later = sorted(
        (u for u in upcoming if u.year == year or (year == shown[0] and u.year not in shown)),
        key=lambda u: u.shown_from,
    )
    ages = _age_range(group)
    note = ""
    if ages and len(group) > 1:
        note = t["year_note"].format(n=len(group), low=ages[0], high=ages[1])
    elif not group:
        note = t["year_empty"]
    blocks = "".join(_venue_block(s, t) for s in group)
    trend = trend_table(sites, upcoming, t) if len(shown) > 1 else ""
    return (
        f'<section class="hero"><h1>{escape(hero(group, t))}</h1>'
        f"<p>{escape(t['lede_index'])}</p></section>"
        f"{trend}"
        f"{year_tabs(shown, year, t)}"
        f'<p class="year-note">{escape(note)}</p>'
        + (f'<ul class="venues">{blocks}</ul>' if blocks else "")
        + _upcoming_note(later, t, wait_days)
    )


def other_years(site: dict[str, Any], sites: list[dict[str, Any]], t: dict[str, Any]) -> str:
    """会议页顶部：回到这一年的列表，以及同一会议其他年份的页面。"""
    year = year_of(site)
    series = series_of(site["venue"])
    others = sorted(
        (s for s in sites if series_of(s["venue"]) == series and s is not site),
        key=year_of,
    )
    back = f'<a href="{year_page(year)}#years">{escape(t["back_year"].format(year=year))}</a>'
    if not others:
        return f'<p class="crumbs">{back}</p>'
    links = " ".join(f'<a href="{s["venue"]}.html">{escape(s["name"])}</a>' for s in others)
    return f'<p class="crumbs">{back}<span>{escape(t["other_years"])} {links}</span></p>'
