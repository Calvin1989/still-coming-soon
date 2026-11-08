import pytest

from scs.links import (
    anonymous_link,
    choose_from_fulltext,
    extract_repos,
    is_page_only,
    is_self_reference,
    link_for,
    promise_without_link,
    quote_with_link,
    resolve,
)
from scs.models import Fragment, FullText, Paper


def full(*frags, status=200):
    return FullText("arxiv:1", status, tuple(Fragment(k, "", tuple(h), t) for k, h, t in frags))


@pytest.mark.parametrize(
    ("sentence", "own"),
    [
        ("Our code is available at", True),
        ("The code will be released at", True),
        ("Code:", True),
        ("We make our models and data publicly available at", True),
        ("The implementation for this paper can be found at", True),
        ("We use the official implementation of DINO", False),
        ("We build on the codebase of Smith et al. available at", False),
        ("Baselines are taken from", False),
        # 以下来自真实论文
        ("Our code builds upon the official implementation11 1", False),
        ("The experiment code is available at", True),
        ("We release all code and data at", True),
        ("We publicly release the code and model checkpoints, made available at", True),
        ("Our codebase would be available at", True),
        ("Code release:", True),
        ("lm-evaluation:", False),
        ("PSLD (", False),
        ("We use the implementation available at", False),
        # 第二轮核对中漏判的真实写法
        ("Code to reproduce these experiments is available at", True),
        ("The python code for GraphSHAP-IQ is available at", True),
        ("Code (fine-tuning and analysis):", True),
        ("The model, data and code will be publicly available at", True),
        (
            "All experiments were conducted using an Nvidia RTX 4090 GPU, the source code is "
            "available at:",
            True,
        ),
        (
            "The code of all the experiments in this paper and the instructions for running can "
            "be found in",
            True,
        ),
        ("An open-source implementation of our method is available at", True),
        ("IterGen code is available at", True),
        ("Code & supp.:", True),
        # 第二轮核对中误判的真实写法
        ("To show the scalability of our method, we train TCM on COYO dataset.", False),
        ("We experiment with our model pre-trained with synthetic GP samples on the Candy", False),
        ("The code of MathVista is available at", False),
        ("We use the original authors' publicly available code:", False),
        ("For ICLM, we follow the GitHub repository.", False),
        ("As an example, our repository (", True),
        (
            "We have open-sourced our code for FlowDec training and inference, along with "
            "pretrained model checkpoints of the FlowDec models listed in this paper, made "
            "available at",
            True,
        ),
    ],
)
def test_is_self_reference(sentence, own):
    assert is_self_reference(sentence) is own


def test_body_baseline_link_not_chosen_footnote_with_context_is():
    f = full(
        ("body", [], "We build on DINO (github.com/facebookresearch/dino). Results follow."),
        ("body", [], "Our implementation will be released at https://github.com/me/x-train."),
    )
    link = choose_from_fulltext(f)
    assert link.repo == "me/x-train"
    assert link.where == "body"
    assert link.future is True


def test_abstract_beats_body():
    f = full(
        ("body", [], "Our code: https://github.com/me/body"),
        ("abstract", [], "We propose X. https://github.com/me/abs"),
    )
    link = choose_from_fulltext(f)
    assert (link.repo, link.where, link.future) == ("me/abs", "abstract", False)


def test_bib_never_chosen():
    assert choose_from_fulltext(full(("bib", [], "Our code https://github.com/a/b"))) is None


def test_href_with_non_url_text():
    f = full(("body", ["https://github.com/me/x"], "Our code is available here."))
    assert choose_from_fulltext(f).repo == "me/x"


def test_resolve_falls_back_to_api_abstract():
    paper = Paper("arxiv:1", "v", "t", "u", "2025-01-01", "Code: https://github.com/me/x")
    assert resolve(paper, full(status=404)).where == "abstract"
    assert resolve(paper, None).repo == "me/x"


def test_anonymous_and_promise_without_link():
    f = full(
        ("body", [], "Code is at https://anonymous.4open.science/r/xyz-123 for review."),
        ("body", [], "Our code will be made publicly available upon acceptance."),
    )
    assert anonymous_link(f) == "anonymous.4open.science/r/xyz-123"
    assert promise_without_link(f) == "Our code will be made publicly available upon acceptance."


def test_would_be_is_future():
    f = full(
        ("abstract", [], "Our codebase would be available at https://github.com/LotuSrc/D2PO.")
    )
    assert choose_from_fulltext(f).future is True


def test_baseline_in_appendix_not_chosen():
    f = full(
        (
            "appendix",
            ["https://github.com/tung-nd/TNP-pytorch.git"],
            "Our code builds upon the official implementation11 1 "
            "https://github.com/tung-nd/TNP-pytorch.git of tnp (Nguyen & Grover, 2022).",
        ),
    )
    assert choose_from_fulltext(f) is None


def test_inline_footnote_marks_are_sentence_boundaries():
    text = (
        "A larger budget favors earlier allocations.99 9 Code is available at "
        "https://github.com/alishiraliGit/hidden-costs."
    )
    link = choose_from_fulltext(full(("body", [], text)))
    assert link.repo == "alishiraliGit/hidden-costs"
    assert link.sentence.startswith("Code is available at github.com/alishiraliGit")


def test_truncated_text_uses_full_name_from_href():
    f = full(
        (
            "abstract",
            ["https://github.com/saccharomycetes/mllms_know"],
            "Our code is available at https://github.com/saccharomycetes/mllms_",
        )
    )
    assert choose_from_fulltext(f).repo == "saccharomycetes/mllms_know"


def test_latex_href_removed_from_quote():
    paper = Paper(
        "arxiv:1",
        "v",
        "t",
        "u",
        "2025-01-01",
        "It works well. Code is available \\href{ https://github.com/q/ChainHOI}{here}.",
    )
    link = link_for(paper)
    assert link.repo == "q/ChainHOI"
    assert link.sentence == "Code is available github.com/q/ChainHOI"


@pytest.mark.parametrize(
    ("sentence", "page_only"),
    [
        ("AAAI-2025; Project page: github.com/ytian73/AIGI-VC", True),
        ("The project website is github.com/a/b", True),
        ("Code and project page: github.com/a/b", False),
        ("Our code is available at github.com/a/b", False),
    ],
)
def test_is_page_only(sentence, page_only):
    assert is_page_only(sentence) is page_only


def test_project_page_link_is_not_a_code_promise():
    paper = Paper(
        "arxiv:1", "v", "t", "u", "2025-01-01", "x\nAAAI 2025; Project page: https://github.com/a/b"
    )
    assert link_for(paper) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # 以下都来自全量正文分析里被误判为"仓库已失效"的真实论文
        (
            "Code: https://github.com/XinXU-USTC/CoLeG-Mathhttps://github.com/XinXU-USTC/CoLeG-Math",
            "XinXU-USTC/CoLeG-Math",
        ),
        (
            "at https://github.com/thu-vis/SE-based_\\_sample_\\_selection..",
            "thu-vis/SE-based_sample_selection",
        ),
        (
            "Our code: https://github.com/LIAAD/portuguese˙vid to promote reproducibility",
            "LIAAD/portuguese_vid",
        ),
        ("Source code: https://github.com/AmayaGS/BioX-CPath00footnotetext", "AmayaGS/BioX-CPath"),
        ("Our code: https://github.com/aio-libs/aiohttp is a library", "aio-libs/aiohttp"),
    ],
)
def test_repo_name_artifacts(text, expected):
    assert extract_repos(text) == [expected]


def test_concatenated_next_word_uses_shorter_name_seen_elsewhere():
    f = full(
        ("body", [], "Our code is available at https://github.com/geon0325/TimeCAPSee Table 2."),
        (
            "body",
            [],
            "Datasets are at https://github.com/geon0325/TimeCAP. The code is on request.",
        ),
    )
    assert choose_from_fulltext(f).repo == "geon0325/TimeCAP"


def test_long_quote_keeps_the_link():
    quote = quote_with_link("Our code is available at " + "x" * 400, "a/b")
    assert quote.startswith("…") and quote.endswith("github.com/a/b") and len(quote) == 320
