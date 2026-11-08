from pathlib import Path

from scs.sources.arxiv_html import parse_html

HTML = (Path(__file__).parent / "fixtures" / "arxiv_paper.html").read_text(encoding="utf-8")


def test_parse_html_kinds_and_scope():
    frags = parse_html(HTML)
    kinds = [(f.kind, f.hrefs) for f in frags]
    assert ("abstract", ("https://github.com/me/x",)) in kinds
    assert ("bib", ("https://github.com/smith/tool",)) in kinds
    assert ("footnote", ("https://github.com/me/x-train",)) in kinds
    # 页脚里 arXiv 自己的链接不在 article 内，不应被提取
    assert all("html_feedback" not in h for f in frags for h in f.hrefs)
    # 没有链接也没有承诺的段落被丢弃
    assert all("unrelated" not in f.text for f in frags)


def test_parse_html_section_title():
    body = [f for f in parse_html(HTML) if f.kind == "body"]
    assert body and body[0].section == "1 Introduction"


def test_parse_html_returns_none_without_article():
    assert parse_html("<html><body><p>hi</p></body></html>") is None


def test_link_with_non_url_text_gets_address_inline():
    html = (
        '<article class="ltx_document"><p class="ltx_p">Our code is available '
        '<a href="https://github.com/me/x">here</a>. More text.</p></article>'
    )
    (frag,) = parse_html(html)
    assert "available here (https://github.com/me/x)." in frag.text
