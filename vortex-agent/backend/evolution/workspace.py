"""
Isolated candidate workspace.

Preferred: `git worktree add` of the Vortex repo onto a branch
`evolution/vNNN-...` under the release directory.

Fallback (no git / worktree failure): copy evolvable modules only.
Never writes into the production working tree.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional


COMPILER_REL = Path("vortex-agent/backend/evolution/compiler.py")
HARNESS_REL = Path("vortex-agent/backend/evolution/harness.py")
BACKEND_REL = Path("vortex-agent/backend")


def find_repo_root(start: Path = None) -> Optional[Path]:
    here = (start or Path(__file__).resolve()).resolve()
    for p in [here, *here.parents]:
        git = p / ".git"
        if git.exists():
            return p
    return None


def _git(repo: Path, *args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class CandidateWorkspace:
    """Create / patch / remove an isolated candidate workspace."""

    def create(self, gen_id: int, dest: Path) -> Dict[str, Any]:
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        repo = find_repo_root()
        meta: Dict[str, Any] = {
            "worktree_dir": None,
            "git_branch": None,
            "repo_root": str(repo) if repo else None,
            "workspace_mode": "fallback_copy",
            "workspace_error": None,
        }
        if not repo:
            meta["workspace_error"] = "not a git checkout"
            self._fallback_copy(dest)
            return meta

        branch = f"evolution/v{int(gen_id):03d}-{os.getpid()}-{int(time.time()) % 100000}"
        worktree = dest / "worktree"
        if worktree.exists():
            shutil.rmtree(worktree, ignore_errors=True)
        proc = _git(repo, "worktree", "add", "-b", branch, str(worktree), "HEAD")
        if proc.returncode != 0:
            meta["workspace_error"] = (proc.stderr or proc.stdout or "worktree add failed")[:400]
            self._fallback_copy(dest)
            return meta
        meta.update({
            "worktree_dir": str(worktree),
            "git_branch": branch,
            "workspace_mode": "git_worktree",
        })
        return meta

    def apply_source_patch(self, worktree: Path, chained: bool = True, power: bool = True) -> Dict[str, Any]:
        """Edit DEFAULT_OVERLAY flags in the isolated compiler.py — a real code change."""
        compiler = Path(worktree) / COMPILER_REL
        if not compiler.exists():
            return {"applied": False, "error": f"missing {COMPILER_REL}", "diff": ""}
        original = compiler.read_text()
        text = original
        replacements = []
        if chained and '"chained_arithmetic": False' in text:
            text = text.replace('"chained_arithmetic": False', '"chained_arithmetic": True', 1)
            replacements.append("DEFAULT_OVERLAY.compiler.chained_arithmetic False→True")
        if power and '"power_operator": False' in text:
            text = text.replace('"power_operator": False', '"power_operator": True', 1)
            replacements.append("DEFAULT_OVERLAY.compiler.power_operator False→True")
        if text != original:
            compiler.write_text(text)
        diff = ""
        proc = _git(worktree, "diff", "--", str(COMPILER_REL))
        if proc.returncode == 0:
            diff = proc.stdout or ""
        if not diff and text != original:
            diff = (
                f"--- a/{COMPILER_REL}\n+++ b/{COMPILER_REL}\n"
                + "\n".join(f"+ {r}" for r in replacements)
                + "\n"
            )
        return {"applied": bool(replacements), "replacements": replacements, "diff": diff}

    def remove(self, worktree: Optional[str], repo: Optional[str] = None, branch: Optional[str] = None) -> None:
        if not worktree:
            return
        root = Path(repo) if repo else find_repo_root()
        if root:
            _git(root, "worktree", "remove", "--force", str(worktree))
            _git(root, "worktree", "prune")
            if branch:
                _git(root, "branch", "-D", branch)
        shutil.rmtree(worktree, ignore_errors=True)

    def _fallback_copy(self, dest: Path) -> None:
        src = Path(__file__).resolve().parent
        checkout = dest / "checkout"
        checkout.mkdir(parents=True, exist_ok=True)
        for name in ("compiler.py", "harness.py"):
            shutil.copy2(src / name, checkout / name)


def prune_tmp_worktrees() -> None:
    """Drop test worktrees registered under /tmp so the main repo stays clean."""
    root = find_repo_root()
    if not root:
        return
    proc = _git(root, "worktree", "list", "--porcelain")
    path = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif line.startswith("branch ") and path and "/tmp/" in path:
            branch = line.split(" ", 1)[1].replace("refs/heads/", "")
            _git(root, "worktree", "remove", "--force", path)
            _git(root, "branch", "-D", branch)
            path = None
    _git(root, "worktree", "prune")
