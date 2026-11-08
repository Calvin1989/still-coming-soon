import pytest

from scs import config
from scs.classify import classify, find_promise
from scs.models import RepoSnapshot, Status

CFG = config.load().classify


def snap(**kw):
    return RepoSnapshot(repo="a/b", checked_at="2026-01-01T00:00:00+00:00", exists=True, **kw)


@pytest.mark.parametrize(
    ("snapshot", "expected"),
    [
        (snap(ext_bytes={".py": 50_000, ".md": 2_000}), Status.RELEASED),
        (snap(ext_bytes={".py": 5_000}), Status.RELEASED),  # 刚好等于阈值
        (snap(ext_bytes={".py": 4_999}), Status.PARTIAL),  # 差一个字节
        (snap(ext_bytes={".md": 3_000, ".png": 900_000}), Status.EMPTY),  # 只有图片和说明
        (snap(ext_bytes={".md": 3_000, ".jsonl": 4_000_000}), Status.DATA_ONLY),  # 只有数据集
        (snap(ext_bytes={".txt": 200}), Status.EMPTY),  # 一个 requirements.txt 不算数据
        (snap(ext_bytes={".py": 300, ".csv": 900_000}), Status.PARTIAL),  # 有一点代码优先算 partial
        (snap(), Status.EMPTY),  # 一次提交都没有
        (RepoSnapshot("a/b", "t", exists=False), Status.GONE),
        (RepoSnapshot("a/b", "t", exists=False, error="timeout"), Status.UNKNOWN),
    ],
)
def test_status(snapshot, expected):
    assert classify(snapshot, CFG).status == expected


def test_released_repo_has_no_promise_text_even_if_readme_says_soon():
    s = snap(ext_bytes={".py": 50_000}, readme="Training code coming soon")
    assert classify(s, CFG).promise_text == ""


@pytest.mark.parametrize(
    ("readme", "expected"),
    [
        ("# Title\n\n**Code coming soon!**\n", "Code coming soon!"),
        (
            "The code will be released upon acceptance.",
            "The code will be released upon acceptance.",
        ),
        ("代码即将开源，敬请期待", "代码即将开源，敬请期待"),
        ("# Title\nOfficial implementation.", ""),
        (
            "[Read the paper](https://x.org/pdf) (The code will be updated soon.)",
            "The code will be updated soon.",
        ),
        ("Paper accepted. Code will be released soon. Contact us.", "Code will be released soon."),
    ],
)
def test_find_promise(readme, expected):
    assert find_promise(readme, CFG.promise_phrases) == expected
