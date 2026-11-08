import re

from scs.render import render_site
from scs.render_parts import entry_id, human_size, marked

ROW = {
    "paper_id": "arxiv:2501.00001",
    "title": "A <b>bold</b> paper",
    "url": "https://arxiv.org/abs/2501.00001",
    "repo": "me/x",
    "promise_text": "Code coming soon!",
    "paper_sentence": "Our code will be released at github.com/me/x",
    "future": True,
    "where": "abstract",
    "promised_days": 100,
    "last_commit": "2025-01-01",
    "checked_at": "2026-01-01",
    "file_count": 2,
    "listing": [["LICENSE", 1100], ["README.md", 2100]],
}


def site(rows, no_repo=(), key="v1", name="ICLR 2025"):
    return {
        "venue": key,
        "name": name,
        "built_on": "2026-01-02",
        "papers": 10,
        "papers_with_fulltext": 0,
        "checked": len(rows),
        "rows": list(rows),
        "no_repo": list(no_repo),
    }


def rows():
    return [
        {**ROW, "status": "empty"},
        {**ROW, "paper_id": "arxiv:2501.00002", "status": "released", "title": "Done"},
        {**ROW, "paper_id": "arxiv:2501.00003", "status": "released", "title": "Done too"},
    ]


def test_venue_page_shows_evidence_side_by_side(tmp_path):
    render_site([site(rows())], tmp_path)
    html = (tmp_path / "v1.html").read_text(encoding="utf-8")
    assert "A &lt;b&gt;bold&lt;/b&gt; paper" in html
    assert "1 of 3 ICLR 2025 papers that link their own repository still have no code" in html
    # 论文原话里的承诺词被标出，仓库里的文件逐个列出
    assert "<mark>will be released at</mark>" in html
    assert "<td>README.md</td><td>2.1 KB</td>" in html
    assert "<mark>coming soon</mark>" in html
    # 一个方格一篇论文，未兑现的排在前面
    cells = re.findall(r'class="cell (\w+)" href="#', html)
    assert cells == ["empty", "released", "released"]
    # 图例默认只打开未兑现的类别
    assert 'data-statuses="empty" aria-pressed="true"' in html
    assert 'data-statuses="released" aria-pressed="false"' in html


def test_index_compares_venues(tmp_path):
    sites = [site(rows()), site([{**ROW, "status": "released"}], key="v2", name="CVPR 2025")]
    render_site(sites, tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<b>33.3%</b> not delivered<br>1 of 3 papers" in html
    assert "<b>0.0%</b> not delivered<br>0 of 1 papers" in html
    # 按未兑现比例从低到高排列
    assert html.index('href="v2.html"') < html.index('href="v1.html"')
    assert 'href="v1.html#p-2501.00001"' in html  # 方格链接到会议页里的那篇论文
    # 标题直接比较兑现率最高和最低的会议
    assert "At CVPR 2025, 0.0% of papers" in html and "At ICLR 2025, it is 33.3%." in html


def test_no_repo_papers_listed_but_not_in_squares(tmp_path):
    no_repo = [
        {
            "paper_id": "arxiv:3",
            "title": "T",
            "url": "u",
            "kind": "no_link",
            "evidence": "Our code will be released.",
            "promised_days": 5,
        }
    ]
    render_site([site(rows(), no_repo)], tmp_path)
    zh = (tmp_path / "zh" / "v1.html").read_text(encoding="utf-8")
    assert "arXiv 版本写了代码将会发布，但没有给出仓库链接。" in zh
    assert zh.count('class="cell no_repo" href') == 0
    assert 'href="../v1.html"' in zh  # 切换到英文版的同一页
    about = (tmp_path / "zh" / "about.html").read_text(encoding="utf-8")
    assert 'href="../about.html"' in about
    assert (tmp_path / "static" / "fonts" / "stix-two-text-latin-400-normal.woff2").exists()


def test_helpers():
    assert human_size(-1, "> 256 KB") == "> 256 KB"
    assert human_size(950, "") == "950 B"
    assert human_size(2100, "") == "2.1 KB"
    assert entry_id("arxiv:2501.00001") == "p-2501.00001"
    assert marked("Code: github.com/a/b") == "<mark>Code:</mark> github.com/a/b"
    assert marked("nothing here <b>") == "nothing here &lt;b&gt;"
