"""根据仓库事实判定状态。纯函数，不联网；改了配置可以直接重新判定，不用重新检查仓库。"""

from __future__ import annotations

import re

from scs.config import ClassifyConfig
from scs.models import RepoSnapshot, Status, Verdict

# 句子边界：中英文句号、问号、感叹号、括号
_SENTENCE_END = re.compile(r"[.!?。！？()（）\[\]]")


def bytes_of(snapshot: RepoSnapshot, extensions: frozenset[str]) -> int:
    return sum(n for ext, n in snapshot.ext_bytes.items() if ext in extensions)


def classify(snapshot: RepoSnapshot, cfg: ClassifyConfig) -> Verdict:
    if snapshot.error:
        return Verdict(Status.UNKNOWN)
    if not snapshot.exists:
        return Verdict(Status.GONE)
    code = bytes_of(snapshot, cfg.code_extensions)
    if code >= cfg.min_code_bytes:
        return Verdict(Status.RELEASED)
    if code > 0:
        status = Status.PARTIAL
    elif bytes_of(snapshot, cfg.data_extensions) >= cfg.min_data_bytes:
        status = Status.DATA_ONLY
    else:
        status = Status.EMPTY
    return Verdict(status, promise_text=find_promise(snapshot.readme, cfg.promise_phrases))


def find_promise(readme: str, phrases: tuple[re.Pattern[str], ...]) -> str:
    """返回 README 里第一处承诺开源的那句话（去掉 Markdown 符号），没有则返回空字符串。"""
    for line in readme.splitlines():
        for p in phrases:
            m = p.search(line)
            if m:
                return _sentence_around(line, m.start(), m.end())
    return ""


def _sentence_around(line: str, start: int, end: int) -> str:
    """从命中位置向两边扩展到句子边界。"""
    left = max((m.end() for m in _SENTENCE_END.finditer(line, 0, start)), default=0)
    right_match = _SENTENCE_END.search(line, end)
    right = right_match.end() if right_match else len(line)
    sentence = line[left:right].strip(" ()（）[]")
    sentence = re.sub(r"[#*>`_]+", " ", sentence)
    return " ".join(sentence.split())[:200]
