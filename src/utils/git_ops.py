"""Git operations for autoresearch (branch / commit / merge / reset)."""
import subprocess
from pathlib import Path
from typing import List, Optional

from utils.logging_utils import get_logger

logger = get_logger("git_ops")


def _run(args: List[str], cwd: Optional[Path] = None, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def current_branch(cwd: Optional[Path] = None) -> str:
    return _run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)


def has_changes(cwd: Optional[Path] = None) -> bool:
    out = _run(["status", "--porcelain"], cwd=cwd)
    return bool(out.strip())


def create_branch(name: str, cwd: Optional[Path] = None) -> None:
    logger.info(f"Creating branch {name}")
    _run(["checkout", "-b", name], cwd=cwd)


def checkout(branch: str, cwd: Optional[Path] = None) -> None:
    _run(["checkout", branch], cwd=cwd)


def add(paths: List[str], cwd: Optional[Path] = None) -> None:
    _run(["add", *paths], cwd=cwd)


def commit(message: str, cwd: Optional[Path] = None) -> None:
    _run(["commit", "-m", message], cwd=cwd)


def merge(branch: str, cwd: Optional[Path] = None, no_ff: bool = True) -> None:
    args = ["merge", branch]
    if no_ff:
        args.insert(1, "--no-ff")
    args += ["-m", f"autoresearch: merge {branch}"]
    _run(args, cwd=cwd)


def delete_branch(branch: str, cwd: Optional[Path] = None, force: bool = True) -> None:
    flag = "-D" if force else "-d"
    _run(["branch", flag, branch], cwd=cwd, check=False)


def reset_hard(ref: str = "HEAD", cwd: Optional[Path] = None) -> None:
    _run(["reset", "--hard", ref], cwd=cwd)


def stash(cwd: Optional[Path] = None) -> None:
    _run(["stash", "push", "-u", "-m", "autoresearch-stash"], cwd=cwd, check=False)


def stash_pop(cwd: Optional[Path] = None) -> None:
    _run(["stash", "pop"], cwd=cwd, check=False)


def head_sha(cwd: Optional[Path] = None) -> str:
    return _run(["rev-parse", "HEAD"], cwd=cwd)
