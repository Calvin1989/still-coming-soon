"""读取 config.toml。其他模块只通过这里拿配置。"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass(frozen=True)
class VenueConfig:
    key: str
    name: str
    conference_date: str
    arxiv_query: str
    include: tuple[re.Pattern[str], ...]
    exclude: tuple[re.Pattern[str], ...]


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


def _patterns(items: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in items)


def load(path: Path = DEFAULT_PATH) -> Config:
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
    )
