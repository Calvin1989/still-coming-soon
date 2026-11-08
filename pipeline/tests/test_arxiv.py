from pathlib import Path

import pytest

from scs import config
from scs.sources.arxiv import is_accepted, parse_atom, strip_version, to_papers

VENUE = config.load().venues["iclr2025"]
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("comment", "accepted"),
    [
        ("ICLR 2025", True),
        ("Accepted at ICLR 2025 (Spotlight)", True),
        ("ICLR '25 Spotlight", True),
        ("Published as a conference paper at ICLR2025", True),
        ("Accepted to International Conference on Learning Representations (ICLR) 2025", True),
        ("To appear in International Conference on Learning Representations (ICLR), 2025", True),
        ("Accepted by ICLR'2025", True),
        ("ICLR-2025, camera-ready version", True),
        ("Accepted at ICLR 2025. Best Paper Award at the ICML 2024 Workshop on X", True),
        ("ICLR 2025 camera-ready. Previously presented at ICML 2023 Workshop", True),
        ("Published at the ICLR 2025 Workshop on Reasoning", False),
        ("Under review at ICLR 2025", False),
        ("Submitted to ICLR 2025", False),
        ("ICLR 2025 Workshop on Foundation Models", False),
        ("Rejected from ICLR 2025, accepted at ICML 2025", False),
        ("ICLR 2024", False),
        ("NeurIPS 2025", False),
    ],
)
def test_is_accepted(comment, accepted):
    assert is_accepted(comment, VENUE) is accepted


def test_strip_version():
    assert strip_version("2302.02182v3") == "2302.02182"
    assert strip_version("2302.02182") == "2302.02182"
    assert strip_version("hep-ph/0612370v1") == "hep-ph/0612370"


def test_parse_atom_and_filter():
    entries, total = parse_atom((FIXTURES / "arxiv_page.xml").read_text(encoding="utf-8"))
    assert total == 2
    papers = to_papers(entries, VENUE)
    assert [p.paper_id for p in papers] == ["arxiv:2501.00001"]
    p = papers[0]
    assert p.published == "2025-01-23"
    assert "github.com/a/b" in p.text


VENUES = config.load().venues


@pytest.mark.parametrize(
    ("venue", "comment", "accepted"),
    [
        ("acl2025", "Accepted to ACL 2025 main conference", True),
        ("acl2025", "NAACL 2025", False),
        ("acl2025", "EACL 2025 (long paper)", False),
        ("acl2025", "Findings of ACL 2025", False),
        ("emnlp2025", "Accepted to EMNLP 2025 Findings", False),
        ("acmmm2025", "Accepted by ACM MM 2025", True),
        ("acmmm2025", "MM '25, October 27-31, 2025, Dublin, Ireland", True),
        ("acmmm2025", "ICMM 2025", False),
        ("acmmm2025", "MMM 2025", False),
        ("neurips2025", "NeurIPS 2025 Datasets and Benchmarks Track", True),
        ("ijcai2025", "IJCAI-25", True),
        ("iccv2025", "ICCV 2025 Workshop on X", False),
        ("neurips2025", "Accepted in NeurIPS (2025)", True),
        ("emnlp2025", "Accepted at EMNLP* 2025", True),
        ("acmmm2025", "Accepted by ACM MM(2025)", True),
    ],
)
def test_other_venues(venue, comment, accepted):
    assert is_accepted(comment, VENUES[venue]) is accepted
