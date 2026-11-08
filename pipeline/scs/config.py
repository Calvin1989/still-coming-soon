"""读取 config.toml。其他模块只通过这里拿配置。"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"
# daily 从 ccfddl 发现的新会议日期（见 scs.schedule），提交在仓库里
DEFAULT_SCHEDULE = Path(__file__).resolve().parents[2] / "data" / "schedule.json"


@dataclass(frozen=True)
class VenueConfig:
    key: str
    name: str
    conference_date: str
    arxiv_query: str
    include: tuple[re.Pattern[str], ...]
    exclude: tuple[re.Pattern[str], ...]

    @property
    def year(self) -> str:
        return self.conference_date[:4]

    def held(self, today: date) -> bool:
        """会议已经开幕：可以开始抓论文了。"""
        return date.fromisoformat(self.conference_date) <= today

    def shown_from(self, wait_days: int) -> date:
        """开幕满 wait_days 天的那一天：从这天起在网站上展示。"""
        return date.fromisoformat(self.conference_date) + timedelta(days=wait_days)

    def due(self, today: date, wait_days: int) -> bool:
        return self.shown_from(wait_days) <= today


@dataclass(frozen=True)
class ClassifyConfig:
    min_code_bytes: int
    code_extensions: frozenset[str]
    min_data_bytes: int
    data_extensions: frozenset[str]
    promise_phrases: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class ProbeConfig:
    workers: int
    timeout_seconds: int
    blob_limit_bytes: int
    readme_chars: int
    max_listing_files: int


@dataclass(frozen=True)
class Config:
    venues: dict[str, VenueConfig]
    classify: ClassifyConfig
    probe: ProbeConfig
    repo_url: str
    wait_days: int
    # 自动发现日期：会议系列（iclr、cvpr…）→ ccfddl 里的文件路径
    auto_series: dict[str, str]
    # 由 schedule.json 自动生成的会议（其余都是 config.toml 里手写的）
    auto_keys: frozenset[str] = frozenset()

    def held_venues(self, today: date) -> list[str]:
        return [k for k, v in self.venues.items() if v.held(today)]

    def due_venues(self, today: date) -> list[str]:
        return [k for k, v in self.venues.items() if v.due(today, self.wait_days)]


def _patterns(items: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in items)


def series_of(venue_key: str) -> str:
    """同一个会议不同年份的共同部分：iclr2025 → iclr。"""
    return re.sub(r"\d{4}$", "", venue_key)


def shift_year(text: str, old: str, new: str) -> str:
    """把文本里的年份 old 换成 new，包括简写：2026 → 2027，'26 → '27，(?:20)?26 → (?:20)?27。"""
    return re.sub(rf"(?<!\d)(20)?{old[2:]}(?!\d)", lambda m: (m.group(1) or "") + new[2:], text)


def derive(template: VenueConfig, year: str, conference_date: str) -> VenueConfig:
    """用同一会议另一年的设置生成新的一年：检索词、匹配规则里的年份换掉，排除规则不变。"""
    old = template.key[-4:]
    return VenueConfig(
        key=series_of(template.key) + year,
        name=shift_year(template.name, old, year),
        conference_date=conference_date,
        arxiv_query=shift_year(template.arxiv_query, old, year),
        include=tuple(
            re.compile(shift_year(p.pattern, old, year), p.flags) for p in template.include
        ),
        exclude=template.exclude,
    )


def auto_venues(
    manual: dict[str, VenueConfig], schedule: dict[str, dict]
) -> dict[str, VenueConfig]:
    """schedule.json 里记录的、config.toml 没有手写的会议。模板是同一会议更早的最近一年。"""
    out = {}
    for key, entry in schedule.items():
        if key in manual:
            continue
        year = key[-4:]
        earlier = [
            v for v in manual.values() if series_of(v.key) == series_of(key) and v.key[-4:] < year
        ]
        if earlier:
            template = max(earlier, key=lambda v: v.key)
            out[key] = derive(template, year, entry["conference_date"])
    return out


def load(path: Path = DEFAULT_PATH, schedule_path: Path = DEFAULT_SCHEDULE) -> Config:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    venues = {
        key: VenueConfig(
            key=key,
            name=v["name"],
            conference_date=v["conference_date"],
            arxiv_query=v["arxiv_query"],
            include=_patterns(v["include"]),
            exclude=_patterns(v["exclude"]),
        )
        for key, v in raw["venues"].items()
    }
    schedule = (
        json.loads(schedule_path.read_text(encoding="utf-8")) if schedule_path.exists() else {}
    )
    auto = auto_venues(venues, schedule)
    venues.update(auto)
    c = raw["classify"]
    p = raw["probe"]
    return Config(
        venues=venues,
        classify=ClassifyConfig(
            min_code_bytes=c["min_code_bytes"],
            code_extensions=frozenset(e.lower() for e in c["code_extensions"]),
            min_data_bytes=c["min_data_bytes"],
            data_extensions=frozenset(e.lower() for e in c["data_extensions"]),
            promise_phrases=_patterns(c["promise_phrases"]),
        ),
        probe=ProbeConfig(**p),
        repo_url=raw.get("site", {}).get("repo_url", ""),
        wait_days=raw.get("schedule", {}).get("wait_days", 0),
        auto_series=raw.get("auto", {}).get("series", {}),
        auto_keys=frozenset(auto),
    )
