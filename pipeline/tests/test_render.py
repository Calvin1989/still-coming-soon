import re

from scs.render import render_site
from scs.render_index import Upcoming
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


def site(rows, no_repo=(), key="v1", name="ICLR 2025", held=""):
    return {
        "venue": key,
        "name": name,
        "conference_date": held,
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


def test_year_pages_and_trend_table(tmp_path):
    sites = [
        site(rows(), key="iclr2025", name="ICLR 2025", held="2025-04-24"),
        site(rows(), key="aaai2026", name="AAAI 2026", held="2026-01-01"),
        site([{**ROW, "status": "released"}], key="iclr2026", name="ICLR 2026", held="2026-01-01"),
    ]
    upcoming = [
        Upcoming("eccv2026", "ECCV 2026", "2026", "2026-12-07"),
        Upcoming("aaai2027", "AAAI 2027", "2027", "2027-05-17"),
    ]
    render_site(sites, tmp_path, upcoming=upcoming, wait_days=90)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")

    # 首页是有数据的最新一年；每一年都有自己的页面
    def main(html):
        return html[html.index("<main>") : html.index("</main>")]

    assert main(index) == main((tmp_path / "2026.html").read_text(encoding="utf-8"))
    assert '<a href="2026.html#years" aria-current="page">2026</a>' in index
    # 标题只比较同一年的会议
    assert "At ICLR 2026, 0.0% of papers" in index and "At AAAI 2026, it is 33.3%." in index
    # 对比表：一行一个会议系列，年份从早到晚，还没上线的写上线日期
    table = index[index.index("<table>") : index.index("</table>")]
    assert table.index(">2025<") < table.index(">2026<")
    iclr = table[table.index(">ICLR<") :].split("</tr>")[0]
    assert iclr.count('class="pct"') == 2 and 'href="iclr2025.html"' in iclr
    assert ">from Dec 7<" in table
    # 还没有结果的 2027 年不单独成页、不占一列，列在最新一年的"暂不展示"里
    assert ">2027<" not in index and not (tmp_path / "2027.html").exists()
    assert "ECCV 2026 on 2026-12-07, AAAI 2027 on 2027-05-17" in index
    assert "held 253 days ago" in table  # 2025-04-24 → 2026-01-02
    old = (tmp_path / "2025.html").read_text(encoding="utf-8")
    assert '<a href="2025.html#years" aria-current="page">2025</a>' in old
    assert 'href="aaai2026.html"' in old  # 表里有，下面的方格图里没有
    assert old.count('class="venue"') == 1
    # 会议页链接到同一会议的其他年份
    page = (tmp_path / "iclr2025.html").read_text(encoding="utf-8")
    assert '<a href="2025.html#years">All 2025 conferences</a>' in page
    assert '<a href="iclr2026.html">ICLR 2026</a>' in page
    zh = (tmp_path / "zh" / "index.html").read_text(encoding="utf-8")
    assert ">12 月 7 日上线<" in zh


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


def test_venue_list_is_grouped_and_collapsible(tmp_path):
    from scs.render_parts import tidy_title

    rows_ = [
        {**ROW, "paper_id": "arxiv:1", "title": "A$^3$: Empty one", "status": "empty"},
        {**ROW, "paper_id": "arxiv:2", "title": "Gone one", "status": "gone"},
        {**ROW, "paper_id": "arxiv:3", "title": "Released one", "status": "released"},
    ]
    render_site([site(rows_, key="v1")], tmp_path)
    html = (tmp_path / "v1.html").read_text(encoding="utf-8")
    # 按状态分组，顺序和图例一致；每组有数量
    assert (
        html.index('data-group="empty"')
        < html.index('data-group="gone"')
        < html.index('data-group="released"')
    )
    assert "Empty repository <b>1</b>" in html

    # 没兑现的可以展开看证据；已开源的只有一行，没有展开内容
    def item(pid):
        start = html.rindex("<li", 0, html.index(f'id="{pid}"'))
        return html[start : html.index("</li>", start)]

    assert "<details><summary>" in item("p-1") and 'class="evidence"' in item("p-1")
    assert "<details>" not in item("p-3") and 'class="entry plain"' in item("p-3")
    # 标题里的 LaTeX 整理成能读的文字
    assert "A³: Empty one" in html
    assert 'class="expand"' in html and 'class="list-head"' in html
    assert tidy_title(r"$\beta$-DPO with $O(n \log n)$") == "β-DPO with O(n log n)"
    assert tidy_title(r"$C^2M^3$ and (FL)$^2$") == "C²M³ and (FL)²"
    assert tidy_title(r"\textsc{Gaze} Net") == "Gaze Net"
