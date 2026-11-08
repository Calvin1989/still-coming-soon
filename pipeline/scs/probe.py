"""检查仓库：用 git 浅克隆只拿最新一次提交的文件列表，不占 GitHub API 次数。

所有调用 git 的代码都在这个文件里。解析 git 输出的函数是纯函数，单独测试。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import PurePosixPath

from scs.checklist import extract_tasks, present_kinds
from scs.config import ProbeConfig
from scs.models import RepoSnapshot

# git 克隆失败时，stderr 里出现这些说明仓库不存在或不公开
_NOT_FOUND_MARKERS = ("could not read username", "repository not found")
_GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "GCM_INTERACTIVE": "never"}


def probe_many(repos: list[str], cfg: ProbeConfig) -> list[RepoSnapshot]:
    with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        return list(pool.map(lambda r: probe(r, cfg), repos))


def probe(repo: str, cfg: ProbeConfig) -> RepoSnapshot:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            clone = _git(
                [
                    "clone",
                    "--quiet",
                    "--depth",
                    "1",
                    "--no-checkout",
                    f"--filter=blob:limit={cfg.blob_limit_bytes}",
                    f"https://github.com/{repo}.git",
                    tmp,
                ],
                cwd=None,
                timeout=cfg.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return RepoSnapshot(repo=repo, checked_at=now, exists=False, error="timeout")
        if clone.returncode != 0:
            if is_not_found(clone.stderr):
                return RepoSnapshot(repo=repo, checked_at=now, exists=False)
            return RepoSnapshot(repo=repo, checked_at=now, exists=False, error=_short(clone.stderr))
        return _inspect(repo, tmp, now, cfg)


def _inspect(repo: str, path: str, now: str, cfg: ProbeConfig) -> RepoSnapshot:
    tree = _git(["ls-tree", "-r", "HEAD"], cwd=path)
    if tree.returncode != 0:  # 仓库存在但一次提交都没有
        return RepoSnapshot(repo=repo, checked_at=now, exists=True)
    sizes = parse_object_sizes(
        _git(["cat-file", "--batch-check", "--batch-all-objects"], cwd=path).stdout
    )
    files = parse_tree(tree.stdout)
    readme = _read_readme(files, path)
    tasks = extract_tasks(readme)
    listing = file_listing(files, sizes) if len(files) <= cfg.max_listing_files else ()
    last_commit = _git(["log", "-1", "--format=%cI"], cwd=path).stdout.strip()
    return RepoSnapshot(
        repo=repo,
        checked_at=now,
        exists=True,
        ext_bytes=ext_bytes(files, sizes, cfg.blob_limit_bytes),
        file_count=len(files),
        last_commit=last_commit,
        readme=readme[: cfg.readme_chars],
        listing=listing,
        tasks=tasks,
        present_kinds=present_kinds(files, readme) if tasks else (),
    )


def _read_readme(files: dict[str, str], path: str) -> str:
    """完整的 README（发布清单常在后半部分）；快照里只存开头。"""
    oid = readme_oid(files)
    if not oid:
        return ""
    out = _git(["cat-file", "-p", oid], cwd=path)
    return out.stdout if out.returncode == 0 else ""


def _git(args: list[str], cwd: str | None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _short(stderr: str) -> str:
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    return lines[-1][:200] if lines else "unknown error"


# ---------- 以下是纯函数 ----------


def is_not_found(stderr: str) -> bool:
    s = stderr.lower()
    return any(m in s for m in _NOT_FOUND_MARKERS)


def parse_tree(ls_tree_output: str) -> dict[str, str]:
    """解析 `git ls-tree -r HEAD`，返回 {路径: blob 对象 id}。子模块等非 blob 条目忽略。"""
    files = {}
    for line in ls_tree_output.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and parts[1] == "blob":
            files[path] = parts[2]
    return files


def parse_object_sizes(batch_check_output: str) -> dict[str, int]:
    """解析 `git cat-file --batch-check --batch-all-objects`，返回 {对象 id: 大小}。"""
    sizes = {}
    for line in batch_check_output.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])
    return sizes


def ext_bytes(files: dict[str, str], sizes: dict[str, int], missing_size: int) -> dict[str, int]:
    """按扩展名汇总文件大小。没下载内容的大文件按 missing_size 计（实际只会更大）。"""
    totals: dict[str, int] = defaultdict(int)
    for path, oid in files.items():
        ext = PurePosixPath(path).suffix.lower() or "(none)"
        totals[ext] += sizes.get(oid, missing_size)
    return dict(sorted(totals.items()))


def file_listing(files: dict[str, str], sizes: dict[str, int]) -> tuple[tuple[str, int], ...]:
    """按路径排序的 [(路径, 大小)]；没下载内容的大文件大小记为 -1。"""
    return tuple((path, sizes.get(oid, -1)) for path, oid in sorted(files.items()))


def readme_oid(files: dict[str, str]) -> str:
    """根目录下的 README（任意大小写、任意扩展名）。"""
    for path, oid in files.items():
        if "/" not in path and PurePosixPath(path).stem.lower() == "readme":
            return oid
    return ""
