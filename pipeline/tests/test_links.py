import pytest

from scs.links import extract_repos, link_for
from scs.models import Paper


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Code: https://github.com/pouyahmdn/LCPO.", ["pouyahmdn/LCPO"]),
        ("see github.com/a-b/c.d_e, and https://github.com/x/y.git", ["a-b/c.d_e", "x/y"]),
        ("https://github.com/x/y and again https://www.github.com/X/Y/tree/main", ["x/y"]),
        ("project page https://foo.github.io/bar", []),
        ("https://github.com/orgs/acme/repositories", []),
        ("(https://github.com/owner/repo)", ["owner/repo"]),
        ("no links here", []),
        (r"at https://github.com/JungHunOh/AWS\_ICLR2025.git", ["JungHunOh/AWS_ICLR2025"]),
    ],
)
def test_extract_repos(text, expected):
    assert extract_repos(text) == expected


def _paper(text):
    return Paper("arxiv:1", "v", "t", "u", "2025-01-01", text)


def test_link_for_takes_first_repo():
    link = link_for(_paper("ours: github.com/a/ours; baseline: github.com/b/base"))
    assert link.repo == "a/ours"
    assert link.all_repos == ("a/ours", "b/base")


def test_link_for_none_without_repo():
    assert link_for(_paper("nothing")) is None
