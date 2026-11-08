"""论文来源的统一接口。加一个来源 = 在 sources/ 里加一个实现这个接口的文件。"""

from __future__ import annotations

from typing import Protocol

from scs.models import Paper


class Source(Protocol):
    def fetch(self) -> list[Paper]:
        """返回某个会议的录用论文。"""
        ...
