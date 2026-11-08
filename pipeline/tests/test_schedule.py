import json

import pytest

from scs import config, schedule
from scs.sources.ccfddl import parse_dates, start_date

YAML = """
- title: EMNLP
  confs:
    - year: 2026
      id: emnlp26
      timeline:
        - deadline: '2026-05-25 23:59:59'
      date: October 25-27, 2026
      place: Budapest, Hungary (Hybrid)
    - year: 2027
      id: emnlp27
      date: 'November 3-5, 2027'
    - year: 2028
      id: emnlp28
      date: TBD
"""


def test_parse_dates():
    assert parse_dates(YAML) == {
        "2026": "October 25-27, 2026",
        "2027": "November 3-5, 2027",
        "2028": "TBD",
    }


@pytest.mark.parametrize(
    ("text", "year", "expected"),
    [
        ("February 16-23, 2027", "2027", "2027-02-16"),
        ("July 31 - August 6, 2027", "2027", "2027-07-31"),
        ("February 27-March 2, 2025", "2025", "2025-02-27"),
        ("May 07-10, 2024", "2024", "2024-05-07"),
        ("December 8-10 (Sydney), December 9-11 (Atlanta and Paris), 2026", "2026", "2026-12-08"),
        ("TBD", "2028", None),
        ("November 3-5, 2027", "2028", None),  # 年份对不上
        ("Smarch 3-5, 2027", "2027", None),
    ],
)
def test_start_date(text, year, expected):
    assert start_date(text, year) == expected


def test_shift_year():
    shift = config.shift_year
    assert shift('''co:"ICLR 2026" OR co:ICLR2026 OR co:"ICLR'26"''', "2026", "2027") == (
        '''co:"ICLR 2027" OR co:ICLR2027 OR co:"ICLR'27"'''
    )
    assert shift(r"ICLR[\s,'’()*@-]*(?:20)?26\b", "2026", "2027") == (
        r"ICLR[\s,'’()*@-]*(?:20)?27\b"
    )
    assert shift('co:"ACM MM26" OR co:"MM \'26"', "2026", "2027") == 'co:"ACM MM27" OR co:"MM \'27"'
    assert shift("ICCV 2025", "2025", "2027") == "ICCV 2027"


def test_load_adds_venues_from_schedule(tmp_path):
    path = tmp_path / "schedule.json"
    path.write_text(json.dumps({"emnlp2027": {"conference_date": "2027-11-03"}}))
    cfg = config.load(schedule_path=path)
    v = cfg.venues["emnlp2027"]
    assert "emnlp2027" in cfg.auto_keys and "emnlp2026" not in cfg.auto_keys
    assert (v.name, v.conference_date) == ("EMNLP 2027", "2027-11-03")
    assert '"EMNLP 2027"' in v.arxiv_query and "2026" not in v.arxiv_query
    assert any(p.search("Accepted at EMNLP 2027") for p in v.include)
    assert not any(p.search("Accepted at EMNLP 2026") for p in v.include)
    assert v.exclude == cfg.venues["emnlp2026"].exclude
    # 手写的会议优先，schedule.json 里同名的忽略
    path.write_text(json.dumps({"iclr2027": {"conference_date": "2030-01-01"}}))
    assert config.load(schedule_path=path).venues["iclr2027"].conference_date == "2027-04-26"


def test_discover_and_merge():
    cfg = config.load()
    manual = {k: v for k, v in cfg.venues.items() if k not in cfg.auto_keys}

    def fetch(path):
        if path == "CG/mm":
            raise OSError("offline")
        return YAML

    found, failed = schedule.discover({"emnlp": "AI/emnlp", "acmmm": "CG/mm"}, manual, fetch)
    assert found == {
        "emnlp2027": {
            "conference_date": "2027-11-03",
            "said": "November 3-5, 2027",
            "source": "AI/emnlp",
        }
    }
    assert failed == ["acmmm"]
    old = {"acmmm2027": {"conference_date": "2027-10-20"}, "emnlp2027": {"conference_date": "x"}}
    merged = schedule.merge(old, found, failed)
    assert list(merged) == ["acmmm2027", "emnlp2027"]
    assert merged["emnlp2027"]["conference_date"] == "2027-11-03"
