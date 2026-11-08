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


def test_gist_and_placeholder_links_are_not_repositories():
    from scs.links import extract_repos

    assert extract_repos("found at https://gist. github.com/alex/b16b0b29b6d0a340") == []
    assert extract_repos("see https://gist.github.com/alex/b16b0b29") == []
    assert extract_repos("We also release the training code github.com/xxx/xxx") == []


def test_placeholder_link_counts_as_anonymous():
    from scs.links import anonymous_link
    from scs.models import Fragment, FullText

    full = FullText("arxiv:1", 200, (Fragment("body", "", (), "code: github.com/xxx/xxx"),))
    assert anonymous_link(full) == "github.com/xxx/xxx"


def test_fallback_repos():
    from scs.links import fallback_repos
    from scs.models import RepoLink

    def link(repo, *others):
        return RepoLink("arxiv:1", repo, (repo, *others))

    assert fallback_repos(link("fkluger/parsacare", "fkluger/parsac")) == ["fkluger/parsac"]
    assert fallback_repos(link("unibo-nlp/medgenie", "disi-unibo-nlp/medgenie")) == [
        "disi-unibo-nlp/medgenie"
    ]
    # 别人的仓库不当备选
    assert fallback_repos(link("mindspore-lab/mindone", "YuchuanTian/AIGC_text_detector")) == []
    assert fallback_repos(link("lab/Reasoning-Affects-LLM-JudgeCode")) == [
        "lab/Reasoning-Affects-LLM-Judge"
    ]
    assert fallback_repos(link("lab/NeuralCode")) == ["lab/Neural"]
    assert fallback_repos(link("sxq/Heteroscedastic-PL", "sxq11/Heteroscedastic-PL")) == [
        "sxq11/Heteroscedastic-PL"
    ]
    long = "elu-lab/ICML2026-Diagnosing-the-Reliability-of-LLM-as-a-Judge-via-Item-Response-Theory"
    assert fallback_repos(link("elu-lab/IRT-Judge", long)) == [long]
    assert fallback_repos(link("o/BAREC-2025", "o/BAREC_2025")) == ["o/BAREC_2025"]
    # 同一作者的另一个项目不算
    assert fallback_repos(link("jian0805/ReflectionV", "jian0805/ClearVQA")) == []
    assert fallback_repos(link("DISL-Lab/DREAM-ICLR-26", "DISL-Lab/BRIDGE-Benchmark")) == []
    assert fallback_repos(link("a/PRISM", "b/PRISM")) == []
    assert fallback_repos(link("lab/CODE")) == []
