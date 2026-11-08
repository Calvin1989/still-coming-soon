"""会议公布日期后自动加入。

daily 先运行 `python -m scs schedule`：读 ccfddl 里每个会议系列的日程，
把 config.toml 还没有的年份记到 data/schedule.json。config.load() 会用同一会议
更早一年的设置生成这些会议，之后和手写的会议走同一套流程。
"""

from __future__ import annotations

from collections.abc import Callable

from scs.config import VenueConfig, series_of
from scs.sources.ccfddl import parse_dates, start_date


def discover(
    series: dict[str, str],
    manual: dict[str, VenueConfig],
    fetch: Callable[[str], str],
) -> tuple[dict[str, dict], list[str]]:
    """返回 ({会议: 记录}, 读取失败的会议系列)。

    只收 config.toml 里已经有更早年份的会议系列、且还没手写的年份。
    """
    found: dict[str, dict] = {}
    failed: list[str] = []
    for name, path in series.items():
        years = sorted(v.key[-4:] for v in manual.values() if series_of(v.key) == name)
        if not years:
            continue
        try:
            dates = parse_dates(fetch(path))
        except OSError:
            failed.append(name)
            continue
        for year, text in dates.items():
            key = name + year
            if key in manual or year <= years[0]:
                continue
            if day := start_date(text, year):
                found[key] = {"conference_date": day, "said": text, "source": path}
    return found, failed


def merge(old: dict[str, dict], found: dict[str, dict], failed: list[str]) -> dict[str, dict]:
    """新结果覆盖旧的；读取失败的会议系列保留旧记录。"""
    kept = {k: v for k, v in old.items() if series_of(k) in failed}
    return dict(sorted({**kept, **found}.items()))
