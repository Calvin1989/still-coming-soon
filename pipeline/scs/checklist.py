"""README 里作者自己列的发布清单，例如：

    - [x] Release inference code
    - [ ] Release training code

只作为补充信息显示，不计入未兑现比例。宁可漏标，不冤枉作者：
- 只认标准的 markdown 勾选项；删除线划掉的、HTML 注释里的不算；
- 只认明确的发布承诺：以 Release / Open-source / Upload / Publish 开头，
  或者是 "Training code"、"Checkpoints" 这类短名词；
- 只认四类核心内容：训练代码、模型权重、数据、推理/评测代码。笼统的"某某代码"
  （"Release the code for efficiency analysis"）常是附带的分析，不算；
- 扩展计划不算（more、other datasets、new version、integration、support …），那不是论文的承诺；
- 清单上没勾、但其实已经放了的，当作作者忘了勾：仓库里有对应的代码文件（比如 train.py），
  或者 README 里有模型、数据的下载链接（Hugging Face、网盘、Zenodo、GitHub Releases …）。

检查仓库时（probe）只提取勾选项和"已经放了哪些类别"，存进快照；
筛选和分类在生成网站数据时（build）做，规则改了不用重新检查仓库。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_TASKS = 40  # 每个仓库最多存这么多个勾选项
MAX_TASK_CHARS = 200

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TASK = re.compile(r"^\s{0,8}(?:[-*+]|\d+[.)])\s+\[( |x|X)\]\s+(.+?)\s*$", re.M)

_VERB = re.compile(r"^(?:release|open[- ]?sourc\w*|upload|publish)\b", re.I)
_NOUN = re.compile(
    r"^(?:the\s+)?(?:(?:pre-?)?train(?:ing)?|inference|evaluation|eval|test(?:ing)?|full|source)?\s*"
    r"(?:code|codes|scripts?|checkpoints?|(?:model\s+)?weights|pre-?trained\s+models?|models?"
    r"|datasets?|data)\b",
    re.I,
)
_ARTIFACT = re.compile(
    r"\b(?:code|codes|scripts?|checkpoints?|ckpts?|weights|models?|datasets?|data|annotations?"
    r"|benchmark)\b",
    re.I,
)
_EXTENSION = re.compile(
    r"\b(?:more|other|additional|new(?:er)? versions?|v\d+(?:\.\d+)?|larger|scal(?:e|ing)|support"
    r"|extend\w*|further|future|improved|updated?|optimi[sz]ed|faster|refactor\w*|pypi|docker"
    r"|colab|gradio|web ?ui|online|huggingface demo|api|integrat\w*|variants?|versions?"
    r"|addi?tional|addtional)\b"
    # 在别的数据集上的代码："Code for the nuScenes dataset"
    r"|\bfor\s+(?:the\s+)?\S+\s+(?:dataset|benchmark)",
    re.I,
)

# 名词形式的项（"Dataset …"）如果说的是文档、用法，不是发布承诺
_DOCS = re.compile(
    r"\b(?:guid\w*|instruction\w*|installation|install|preparation|prepare|document\w*|tutorial\w*"
    r"|usage|easier|explain\w*|description|format|structure|details?|specific|is|are)\b",
    re.I,
)

# 类别，按显示顺序。"(?<![\w-])train" 不匹配 pre-trained / pretrained。
KINDS = ("training", "weights", "data", "inference", "code")
_KIND_PATTERNS = {
    "training": re.compile(r"(?<![\w-])train(?:ing)?\b|pre-?training\b|fine-?tun", re.I),
    "weights": re.compile(r"checkpoint|ckpt|weight|pre-?trained|\bmodels?\b", re.I),
    "data": re.compile(r"dataset|\bdata\b|annotation|benchmark", re.I),
    "inference": re.compile(r"inference|\beval|\btest|\bdemo", re.I),
}
# 仓库里有这些代码文件，说明对应类别的代码其实已经放了
_FILE_KINDS = {
    "training": re.compile(r"(?<![a-z])train|finetun|fine_tun", re.I),
    "inference": re.compile(r"infer|demo|predict|eval|test|sample|generat", re.I),
}
# README 里有这些下载链接，说明权重 / 数据可能已经放了（宁可漏标）
_LINK_KINDS = {
    "weights": re.compile(
        r"huggingface\.co/(?!datasets/|spaces/|papers/|docs/|blog/)[\w.-]+/[\w.-]+|hf\.co/"
        r"|drive\.google\.com|pan\.baidu\.com|onedrive|1drv\.ms|dropbox\.com|zenodo\.org"
        r"|releases/download|modelscope\.cn|aliyundrive|box\.com",
        re.I,
    ),
    "data": re.compile(
        r"huggingface\.co/datasets/|drive\.google\.com|pan\.baidu\.com|onedrive|1drv\.ms"
        r"|dropbox\.com|zenodo\.org|kaggle\.com|figshare|releases/download|modelscope\.cn",
        re.I,
    ),
}
_CODE_EXTENSIONS = frozenset(
    {".py", ".sh", ".ipynb", ".cpp", ".cu", ".c", ".js", ".ts", ".m", ".jl", ".r", ".lua"}
)


@dataclass(frozen=True)
class Checklist:
    """一个仓库的发布清单（只含筛选后的发布承诺）。"""

    done: int
    total: int
    open: tuple[str, ...]  # 还没勾的项，原文
    open_kinds: tuple[str, ...]  # 还没勾的项涉及的类别，按 KINDS 的顺序


# ---------- 检查仓库时：提取 ----------


def extract_tasks(readme: str) -> tuple[tuple[bool, str], ...]:
    """README 里所有 markdown 勾选项 [(是否已勾, 文字)]。HTML 注释里的忽略。"""
    text = _COMMENT.sub("", readme)
    tasks = [(mark != " ", item[:MAX_TASK_CHARS]) for mark, item in _TASK.findall(text)]
    return tuple(tasks[:MAX_TASKS])


def present_kinds(paths: Iterable[str], readme: str) -> tuple[str, ...]:
    """已经放了哪些类别：仓库里的代码文件，加上 README 里的下载链接。"""
    found = set(file_kinds(paths))
    found.update(kind for kind, pattern in _LINK_KINDS.items() if pattern.search(readme))
    return tuple(k for k in KINDS if k in found)


def file_kinds(paths: Iterable[str]) -> tuple[str, ...]:
    """仓库里有哪些类别的代码文件（看文件名和所在目录名）。"""
    found = set()
    for path in paths:
        p = PurePosixPath(path)
        if p.suffix.lower() not in _CODE_EXTENSIONS:
            continue
        for kind, pattern in _FILE_KINDS.items():
            if any(pattern.search(part) for part in p.parts):
                found.add(kind)
    return tuple(k for k in KINDS if k in found)


# ---------- 生成网站数据时：筛选、分类 ----------


def clean(text: str) -> str:
    """去掉 markdown 标记、链接地址，留下读得懂的文字。"""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [文字](链接) → 文字
    text = re.sub(r"[*_`]+", "", text)
    return " ".join(text.split()).strip(" .:;-–—")


def is_release_item(text: str) -> bool:
    if "~~" in text:
        return False
    t = clean(text)
    if not t or not _ARTIFACT.search(t) or _EXTENSION.search(t):
        return False
    if _VERB.search(t):
        return True
    return bool(_NOUN.search(t)) and len(t) <= 60 and not _DOCS.search(t)


def kinds_of(text: str) -> tuple[str, ...]:
    found = [k for k, p in _KIND_PATTERNS.items() if p.search(text)]
    return tuple(found) if found else ("code",)


def summarize(tasks: Iterable[tuple[bool, str]], present: Iterable[str] = ()) -> Checklist | None:
    """筛选出发布承诺并汇总；没有发布承诺时返回 None。

    present：已经放了的类别（见 present_kinds）。没勾的项如果只涉及这些类别，
    当作作者忘了勾，算已完成。
    """
    present = set(present)
    done = total = 0
    open_items: list[str] = []
    open_kinds: set[str] = set()
    for ticked, text in tasks:
        if not is_release_item(text):
            continue
        kinds = kinds_of(clean(text))
        if kinds == ("code",):  # 不属于四类核心内容
            continue
        total += 1
        if ticked or set(kinds) <= present:
            done += 1
        else:
            open_items.append(clean(text))
            open_kinds.update(kinds)
    if not total:
        return None
    return Checklist(done, total, tuple(open_items), tuple(k for k in KINDS if k in open_kinds))
