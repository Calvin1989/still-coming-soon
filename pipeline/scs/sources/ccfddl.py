"""会议日期来源：ccfddl/ccf-deadlines（ccfddl.com 的数据，社区维护）。

每个会议一个 YAML 文件，每年一条，例如：
    - year: 2027
      ...
      date: February 16-23, 2027
只用到 year 和 date 两项，所以逐行读，不需要 YAML 库。
"""

from __future__ import annotations

import re
import urllib.request
from datetime import date

URL = "https://raw.githubusercontent.com/ccfddl/ccf-deadlines/main/conference/{path}.yml"

_YEAR = re.compile(r"^\s*-\s*year:\s*(\d{4})\s*$")
_DATE = re.compile(r"^\s*date:\s*['\"]?(.+?)['\"]?\s*$")
_START = re.compile(r"^([A-Za-z]{3,})\.?\s+(\d{1,2})\b")
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
    )
}


def parse_dates(text: str) -> dict[str, str]:
    """{年份: 日期原文}，例如 {"2027": "February 16-23, 2027"}。"""
    found: dict[str, str] = {}
    year = ""
    for line in text.splitlines():
        if m := _YEAR.match(line):
            year = m.group(1)
        elif (m := _DATE.match(line)) and year:
            found[year] = m.group(1)
            year = ""
    return found


def start_date(text: str, year: str) -> str | None:
    """日期原文的第一天，YYYY-MM-DD。写的是 TBD、格式不对或年份对不上时返回 None。"""
    m = _START.match(text.strip())
    if not m or year not in text:
        return None
    month = _MONTHS.get(m.group(1)[:3].lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(m.group(2))).isoformat()
    except ValueError:
        return None


def fetch(path: str, timeout: int = 30) -> str:
    request = urllib.request.Request(URL.format(path=path), headers={"User-Agent": "scs"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read().decode("utf-8")
