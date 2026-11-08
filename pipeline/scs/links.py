"""找出论文自己的仓库链接。纯函数，不联网。

论文正文里常常有很多 GitHub 链接（引用别人的基线代码、用到的工具库），只有作者说
"我们的代码在这里"的那一个才算承诺。判断规则：

1. 摘要、标题区（作者信息、标题脚注）里的链接，直接算论文自己的。
2. 正文、脚注、附录、图表说明里的链接，只有链接前面那句话是在说"我们的代码"时才算，例如
   "Our code is available at …"、"Code: …"、"The code will be released at …"。
3. 参考文献里的链接一律不算。

宁可漏判，不要错判：错判会把别人的仓库算到这篇论文头上。
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace

from scs.models import Fragment, FullText, Paper, RepoLink

_REPO = re.compile(
    r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_RESERVED_OWNERS = {"orgs", "features", "topics", "about", "settings", "marketplace", "sponsors"}
# 作者用来占位的匿名账号（github.com/anonymous/…），不是真仓库
_ANON_OWNER = re.compile(r"^anon(?:ymous|ymized)?(?:[-_]?\w*)?$", re.IGNORECASE)
# 占位符：github.com/xxx/xxx 这类，定稿里忘了换成真链接，和匿名链接同样处理
_PLACEHOLDER_OWNER = re.compile(r"^x{3,}$", re.IGNORECASE)
# gist.github.com/… 是代码片段，不是仓库
_GIST_BEFORE = re.compile(r"gist\.\s*$", re.IGNORECASE)

# "可获取/已发布"一类的词，出现在句子里才说明这句话是在给出代码的位置
_AVAILABLE = (
    r"(?:available|availability|released?|open[- ]?sourced?|found|accessible|accessed|hosted"
    r"|provided|public|publicly|uploaded|shared|located|here|at\s*:?|in\s*:|:|\(\s*$)"
)
# 代码一类的名词（不含数据集：数据集经常是别人的）
_CODE_NOUN = (
    r"(?:code|codes|source code|codebase|code base|implementation|implementations|repository"
    r"|repo|project page|project website|project|code release)"
)
# 句子开头：句首、标点之后、括号之后
_START = r"(?:^|[.!?;:,]\s+|\(\s*)"

# 链接前面这句话在说"我们的代码"
_SELF_REFERENCE = [
    # our code / our models … + 可获取：Our code is available at / our models are released at
    re.compile(
        r"\bour\b[^.]{0,60}\b(?:code|codes|implementation|codebase|repository|repo|project"
        r"|models?|benchmark|datasets?|data|framework|library|toolkit|package|software"
        r"|weights|checkpoints)\b[^.]{0,150}" + _AVAILABLE,
        re.IGNORECASE,
    ),
    # 以"代码"为主语的句子 + 可获取：The code is available at / Code: / The python code for X is …
    # / The model, data and code will be publicly available at / Code (fine-tuning): …
    re.compile(
        _START
        + r"(?:the|all|an?|this)?\s*(?:[\w&,-]+\s+){0,3}?"
        + _CODE_NOUN
        + r"\b(?:\s*\([^)]{0,50}\))?[^.]{0,120}?"
        + _AVAILABLE,
        re.IGNORECASE,
    ),
    # 很短的标签式写法：Code & supp.: / Code and models:
    re.compile(r"\b(?:code|codes|implementation|project)\b.{0,15}:\s*$", re.IGNORECASE),
    # Code to reproduce the experiments … / All code to replicate our results …
    re.compile(r"\bcodes?\s+(?:to|for)\s+(?:reproduc|replicat|run)\w*", re.IGNORECASE),
    # code for this paper / code of all the experiments in this paper
    re.compile(
        r"\b(?:code|implementation)s?\b[^.]{0,60}\b(?:this|the present)\s+(?:paper|work|study)\b",
        re.IGNORECASE,
    ),
    # We release all code and data at / We publicly release … / We make … available at
    re.compile(r"\bwe\s+(?:\w+\s+){0,2}(?:releas|open[- ]?sourc|publish)\w*", re.IGNORECASE),
    re.compile(r"\bwe\s+(?:\w+\s+){0,2}make\b[^.]{0,60}\bavailable\b", re.IGNORECASE),
]
# 出现这些说法，说明链接是作者用到的别人的代码，即使句子里有 "our code" 也不算
_NOT_OWN = re.compile(
    r"\b(?:build[s]?\s+(?:up)?on|built\s+(?:up)?on|based\s+on|adapted\s+from|borrow(?:ed|s)?\s+from"
    r"|taken\s+from|derived\s+from|official\s+(?:implementation|code|repository)"
    r"|provided\s+by|released\s+by|(?:original\s+)?authors['’]?|we\s+use[ds]?|we\s+follow"
    r"|follow(?:ing|ed)?\s+the|using\s+the|implemented\s+(?:with|using|in)|built\s+with"
    r"|we\s+refer(?:red)?|refer\s+to|obtained\s+from|downloaded\s+from|retrieved\s+from"
    r"|(?:code|implementation|repository)s?\s+(?:of|from|by)\s+"
    r"(?!(?:this|our|all|the\s+experiments|these|the\s+present)\b))",
    re.IGNORECASE,
)
_FUTURE = re.compile(
    r"\b(?:will be|would be|to be (?:released|made|open)|upon (?:acceptance|publication)"
    r"|coming soon|soon|after (?:the )?(?:review|acceptance|publication)|forthcoming)\b",
    re.IGNORECASE,
)
_ALWAYS_OWN = {"abstract", "front"}
_NEVER_OWN = {"bib"}
_PRIORITY = {
    "abstract": 0,
    "front": 1,
    "footnote": 2,
    "body": 2,
    "appendix": 3,
    "caption": 4,
    "table": 4,
}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])|(?<=[a-z]{2}[.!?])(?=[A-Z][a-z])|\n+")
_URL_PREFIX = re.compile(r"\s*(?:https?://)?(?:www\.)?$", re.IGNORECASE)


_FOOTNOTE_TAIL = re.compile(r"\d*footnotetext$", re.IGNORECASE)
# LaTeX 颜色命令的残留，和后面的网址粘在一起："BioDetmagentagithub.com/…"
_COLOR_TAIL = re.compile(r"(?:magenta|cyan|blue|teal|purple|violet|orange)$", re.IGNORECASE)
_SCHEME_TAIL = re.compile(r"https?$", re.IGNORECASE)


def _clean_name(name: str, following: str = "") -> str:
    """去掉粘在仓库名后面的东西。following 是原文里紧跟在仓库名后面的几个字符。"""
    name = _FOOTNOTE_TAIL.sub("", name)  # LaTeX 残留："BioX-CPath00footnotetext"
    glued = name.lower().find("github.com")
    if glued > 0:  # 后面粘了另一个网址
        name = _COLOR_TAIL.sub("", name[:glued])
    if following.startswith("://"):  # 两个网址连写："CoLeG-Mathhttps://github.com/…"
        name = _SCHEME_TAIL.sub("", name)
    name = name.rstrip(".,;:_-")
    if name.lower().endswith(".git"):
        name = name[:-4]
    return name


# LaTeX 转成 HTML 后，脚注编号会粘在正文上："allocations.99 9 Code is …"、"available11 1 https…"
_INLINE_FOOTNOTE = re.compile(r"(\d{1,2})\1 \1 ")
_NOTE_PREFIX = re.compile(r"^\s*(\d{1,2}) \1 |[†‡]+\s*(?:footnotetext:)?")


_LATEX_LINK = re.compile(r"\\(?:href|url)\s*\{\s*|(?<=\S)\}\s*\{[^}]*\}")


def _normalize(text: str) -> str:
    # 下划线的各种 LaTeX 写法：\_、_\_（还原后会变成两个下划线）、HTML 版里的 ˙
    text = text.replace("_\\_", "_").replace("\\_", "_").replace("˙", "_")
    text = _LATEX_LINK.sub("", text)  # 摘要里残留的 \href{…}{…}、\url{…}
    text = _INLINE_FOOTNOTE.sub("\n", text)  # 脚注编号处换行，当作句子边界
    return _NOTE_PREFIX.sub(" ", text)


def find_repos(text: str) -> list[tuple[str, int]]:
    """返回 [(owner/name, 在文本中的位置)]，按出现顺序，未去重。"""
    found = []
    text = _normalize(text)
    for m in _REPO.finditer(text):
        owner, name = m.group(1), _clean_name(m.group(2), text[m.end() : m.end() + 3])
        if (
            name
            and owner.lower() not in _RESERVED_OWNERS
            and not _ANON_OWNER.match(owner)
            and not _PLACEHOLDER_OWNER.match(owner)
            and not _GIST_BEFORE.search(text[max(m.start() - 8, 0) : m.start()])
        ):
            found.append((f"{owner}/{name}", m.start()))
    return found


def extract_repos(text: str) -> list[str]:
    """按出现顺序返回去重后的 "owner/name" 列表。"""
    seen: dict[str, str] = {}
    for repo, _ in find_repos(text):
        seen.setdefault(repo.lower(), repo)
    return list(seen.values())


def quote_with_link(sentence: str, repo: str) -> str:
    """网站上展示的论文原话：那句话 + 链接本身。太长时截掉开头，保证链接还在。"""
    quote = " ".join(f"{sentence} github.com/{repo}".split())
    return quote if len(quote) <= 320 else "…" + quote[-319:]


def sentence_before(text: str, pos: int) -> str:
    """链接所在的那句话：从上一个句子结束处到链接为止，最多往前看 300 个字符。"""
    window = _URL_PREFIX.sub("", text[max(0, pos - 300) : pos])
    parts = _SENTENCE_SPLIT.split(window)
    tail = parts[-1] if parts else window
    if len(tail) < 12 and len(parts) > 1:  # 例如 "Code: " 这种太短的，带上前一句
        tail = parts[-2] + " " + tail
    return tail.strip()


_PAGE = re.compile(
    r"project\s*(?:page|website|homepage|site)|\bhomepage\b|\bweb\s?page\b|\bwebsite\b",
    re.IGNORECASE,
)
_CODE_WORD = re.compile(
    r"\bcodes?\b|implementation|codebase|source|repository|\brepo\b|models?\b|weights"
    r"|checkpoints|data(?:sets?)?\b|benchmark",
    re.IGNORECASE,
)


def is_page_only(sentence: str) -> bool:
    """链接只被说成项目主页、没提到代码（"Project page: github.com/…"）。

    这不是代码承诺，不计入统计。
    """
    before_link = sentence.split("github.com/")[0]
    return bool(_PAGE.search(before_link)) and not _CODE_WORD.search(before_link)


def is_self_reference(sentence: str) -> bool:
    if _NOT_OWN.search(sentence):
        return False
    return any(p.search(sentence) for p in _SELF_REFERENCE)


def _candidates(fragment: Fragment) -> Iterable[tuple[str, str]]:
    """一段话里属于论文自己的仓库，返回 [(repo, 那句话)]。"""
    if fragment.kind in _NEVER_OWN:
        return
    text = _normalize(fragment.text)
    from_hrefs = [r for h in fragment.hrefs for r, _ in find_repos(h)]
    in_text = [(_complete(repo, from_hrefs), pos) for repo, pos in find_repos(text)]
    for repo, pos in in_text:
        sentence = sentence_before(text, pos)
        if is_page_only(sentence):
            continue
        if fragment.kind in _ALWAYS_OWN or is_self_reference(sentence):
            yield repo, sentence
    # 链接文字不是网址的情况（例如 "Code is available here" 里的 here 是链接）
    shown = {r.lower() for r, _ in in_text}
    own_context = fragment.kind in _ALWAYS_OWN or is_self_reference(text[:400])
    for repo in from_hrefs:
        if repo.lower() not in shown and own_context:
            yield repo, text[:300]


def _complete(repo: str, href_repos: list[str]) -> str:
    """文字里的仓库名和链接地址里的对不上时，以链接地址为准。

    文字被截断："mllms_" → 地址里是 "mllms_know"；文字粘了后文："TimeCAPSee" → 地址里是 "TimeCAP"。
    """
    r = repo.lower()
    for full in href_repos:
        f = full.lower()
        if f != r and (f.startswith(r) or r.startswith(f)):
            return full
    return repo


_GLUED_WORD = re.compile(r"[A-Z][a-z]")


def _shortest_prefix(repo: str, others: list[str]) -> str:
    """论文别处出现过同一作者下更短的同名仓库时（"TimeCAP" 和 "TimeCAPSee"），用短的那个。

    只在多出来的部分像是粘上来的新单词时才换（"See"）；
    文字被截断的情况（"mllms" 和 "mllms_know"）不换。
    """
    r = repo.lower()
    prefixes = [
        o
        for o in others
        if r.startswith(o.lower()) and len(o) < len(repo) and _GLUED_WORD.match(repo[len(o) :])
    ]
    return min(prefixes, key=len) if prefixes else repo


def choose_from_fulltext(full: FullText) -> RepoLink | None:
    """从正文里挑出论文自己的仓库：位置优先级高的优先，同级按出现顺序。"""
    best: tuple[int, int, str, str, str] | None = None
    order = 0
    all_repos: dict[str, str] = {}
    for frag in full.fragments:
        if frag.kind in _NEVER_OWN:
            continue
        for repo, sentence in _candidates(frag):
            all_repos.setdefault(repo.lower(), repo)
            key = (_PRIORITY.get(frag.kind, 5), order)
            order += 1
            if best is None or key < best[:2]:
                best = (*key, repo, sentence, frag.kind)
    if best is None:
        return None
    _, _, repo, sentence, kind = best
    seen_anywhere = [
        r
        for frag in full.fragments
        if frag.kind not in _NEVER_OWN
        for source in (frag.text, *frag.hrefs)
        for r, _ in find_repos(source)
    ]
    repo = _shortest_prefix(repo, seen_anywhere)
    return RepoLink(
        paper_id=full.paper_id,
        repo=repo,
        all_repos=tuple(all_repos.values()),
        where=kind,
        sentence=quote_with_link(sentence, repo),
        future=bool(_FUTURE.search(sentence)),
    )


def link_for(paper: Paper) -> RepoLink | None:
    """只用 arXiv 接口里的摘要和备注：取第一个不是"项目主页"的链接。"""
    text = _normalize(paper.text)
    candidates = ((repo, sentence_before(text, pos)) for repo, pos in find_repos(paper.text))
    chosen = next(((r, s) for r, s in candidates if not is_page_only(s)), None)
    if chosen is None:
        return None
    repo, sentence = chosen
    return RepoLink(
        paper_id=paper.paper_id,
        repo=repo,
        all_repos=tuple(extract_repos(paper.text)),
        where="abstract",
        sentence=quote_with_link(sentence, repo),
        future=bool(_FUTURE.search(sentence)),
    )


def resolve(paper: Paper, full: FullText | None) -> RepoLink | None:
    """合并两个来源：有正文时以正文为准（正文也包含摘要），正文里找不到再用接口摘要。"""
    if full is not None and full.available:
        chosen = choose_from_fulltext(full)
        if chosen is not None:
            return chosen
    link = link_for(paper)
    if link is not None and full is not None and full.available:
        # 摘要里的网址可能写坏了（"BreuerLabs/E- LDA"），正文里有完整的就用正文的
        in_body = [r for frag in full.fragments for h in frag.hrefs for r, _ in find_repos(h)]
        repo = _complete(link.repo, in_body)
        if repo != link.repo:
            link = replace(link, repo=repo, sentence=link.sentence.replace(link.repo, repo))
    return link


_ANON = re.compile(
    r"anonymous\.4open\.science/r/[\w.-]+|github\.com/(?:anonym\w*|x{3,})/[\w.-]+",
    re.IGNORECASE,
)


def anonymous_link(full: FullText | None) -> str:
    """定稿里仍然只给了匿名评审链接（anonymous.4open.science）或占位链接时返回该链接。"""
    if full is None or not full.available:
        return ""
    for frag in full.fragments:
        if frag.kind in _NEVER_OWN:
            continue
        for source in (frag.text, *frag.hrefs):
            m = _ANON.search(source)
            if m:
                return m.group(0).rstrip(".,;:)")
    return ""


_PROMISE_NO_LINK = re.compile(
    r"\b(?:our\s+)?(?:code|codes|implementation|source code)\b[^.]{0,60}"
    r"\b(?:will be|to be)\s+(?:made\s+)?(?:publicly\s+)?(?:released|available|open[- ]?sourced)",
    re.IGNORECASE,
)


def promise_without_link(full: FullText | None) -> str:
    """正文里说了"代码将会发布"，但那段话里没有任何链接。返回那句话。"""
    if full is None or not full.available:
        return ""
    for frag in full.fragments:
        if frag.kind in _NEVER_OWN or frag.hrefs or "github.com" in frag.text.lower():
            continue
        if "4open.science" in frag.text.lower():
            continue
        m = _PROMISE_NO_LINK.search(frag.text)
        if m:
            start = frag.text.rfind(".", 0, m.start()) + 1
            end = frag.text.find(".", m.end())
            return frag.text[start : end + 1 if end != -1 else None].strip()[:300]
    return ""


# 仓库名后面粘上了下一个词，比如 "Reasoning-Affects-LLM-JudgeCode"
_GLUED_TAIL = re.compile(
    r"^(.*[a-z0-9])(?:Code|Codes|Data|Dataset|Paper|Project|Page|Website|GitHub|Github|Repo)$"
)


_STOPWORDS = frozenset(
    {"a", "an", "and", "as", "for", "in", "of", "on", "the", "to", "via", "with"}
)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]", "", name.lower())


def _words(name: str) -> list[str]:
    return [w for w in re.split(r"[-_.]+", name.lower()) if w]


def _covers(short: str, long: str) -> bool:
    """short 的每个词都出现在 long 里，或是 long 里连续几个词的首字母缩写。

    例如 IRT-Judge 和 …-Judge-via-Item-Response-Theory。
    """
    words = _words(long)
    content = [w for w in words if w not in _STOPWORDS]
    acronyms = {
        "".join(w[0] for w in content[i:j])
        for i in range(len(content))
        for j in range(i + 2, len(content) + 1)
    }
    tokens = _words(short)
    return bool(tokens) and all(t in words or t in acronyms for t in tokens)


def _similar(a: str, b: str) -> bool:
    """两个仓库名是不是同一个东西的不同写法。"""
    na, nb = _norm(a), _norm(b)
    short, long = sorted((na, nb), key=len)
    if len(short) >= 3 and short in long:
        return True
    return _covers(a, b) or _covers(b, a)


def fallback_repos(link: RepoLink) -> list[str]:
    """主链接的仓库不存在时再试的仓库，按顺序。

    论文里经常给出两个写法不同的链接（摘要和正文不一致、改过名、后面粘了单词）。
    只要其中一个有代码，就不算没兑现：宁可漏判，也不冤枉作者。
    候选必须像是同一个仓库，不能是同一作者的另一个项目：
      同一账号，名字相近（parsacare / parsac，IRT-Judge / …-Item-Response-Theory）；
      名字相同，账号相近（sxq / sxq11，unibo-nlp / disi-unibo-nlp）；
      去掉粘连单词后的名字（…-JudgeCode → …-Judge）。
    """
    owner, name = link.repo.split("/", 1)
    out = []
    for other in link.all_repos:
        o, n = other.split("/", 1)
        if other.lower() == link.repo.lower():
            continue
        same_owner = o.lower() == owner.lower()
        if (same_owner and _similar(name, n)) or (_norm(n) == _norm(name) and _similar(owner, o)):
            out.append(other)
    if m := _GLUED_TAIL.match(name):
        out.append(f"{owner}/{m.group(1)}")
    return list(dict.fromkeys(out))
