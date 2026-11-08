"""数据结构定义。只放定义，不放逻辑。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class Paper:
    """一篇被某个会议录用的论文。"""

    paper_id: str  # 例如 "arxiv:2302.02182"
    venue: str  # 例如 "iclr2025"
    title: str
    url: str
    published: str  # 论文首次公开日期，YYYY-MM-DD
    text: str  # 用来提取仓库链接的文本（摘要 + 备注）


@dataclass(frozen=True)
class Fragment:
    """论文正文里的一段话（段落、脚注、表格单元格等），只保留含链接或承诺的段落。"""

    kind: str  # abstract / front / footnote / body / appendix / caption / table / bib
    section: str  # 所在章节标题
    hrefs: tuple[str, ...]  # 段落里链接的地址（链接文字可能不是网址本身）
    text: str


@dataclass(frozen=True)
class FullText:
    """一篇论文正文的提取结果。"""

    paper_id: str
    http_status: int  # 404 表示 arXiv 没有这篇论文的 HTML 版
    fragments: tuple[Fragment, ...]

    @property
    def available(self) -> bool:
        return self.http_status == 200


@dataclass(frozen=True)
class RepoLink:
    """论文自己的仓库链接。"""

    paper_id: str
    repo: str  # "owner/name"，保留论文里的大小写
    all_repos: tuple[str, ...]  # 论文里出现的全部仓库
    where: str = "abstract"  # 链接出现的位置：abstract（arXiv 接口里的摘要）或 Fragment.kind
    sentence: str = ""  # 论文里给出链接的那句话
    future: bool = False  # 这句话是"将会发布"而不是"已经发布"


@dataclass(frozen=True)
class RepoSnapshot:
    """某一时刻观察到的仓库事实。只记事实，不做判断。"""

    repo: str
    checked_at: str  # ISO 时间
    exists: bool
    error: str = ""  # 网络超时等无法判断的情况，exists 此时无意义
    ext_bytes: dict[str, int] = field(default_factory=dict)  # 各扩展名的文件总大小
    file_count: int = 0
    last_commit: str = ""  # 最新一次提交的时间
    readme: str = ""  # README 开头部分
    # 文件列表 [(路径, 大小)]，只在文件不多时保存，网站上用来展示"仓库里到底有什么"。
    # 大小为 -1 表示文件太大、没有下载内容。
    listing: tuple[tuple[str, int], ...] = ()

    @property
    def gone(self) -> bool:
        """确认仓库不存在（不是网络问题）。"""
        return not self.error and not self.exists


class Status(StrEnum):
    RELEASED = "released"  # 已开源
    PARTIAL = "partial"  # 只放了少量代码
    DATA_ONLY = "data_only"  # 只放了数据或模型文件，没有代码
    EMPTY = "empty"  # 仓库还是空的
    GONE = "gone"  # 链接已失效
    UNKNOWN = "unknown"  # 检查失败，下次重试


@dataclass(frozen=True)
class Verdict:
    status: Status
    promise_text: str = ""  # README 里承诺开源的原话，没有则为空
