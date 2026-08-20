"""Shared git sync helpers for consumers of this repo's totranslate.txt.

Any translation script, on any machine, that wants to read or update the
shared queue should follow this discipline:

    git_pull(repo_dir)                      # get the latest state
    ... pick a candidate line, claim it ...
    git_commit_push(repo_dir, "claim: ...")  # publish the claim immediately
    ... do the (possibly slow) translation work ...
    git_commit_push(repo_dir, "result: ...") # publish the final status

git_commit_push() pulls-and-retries on push rejection, so two machines
racing to update the file at the same time resolve safely instead of one
silently overwriting the other.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path


class QueueSyncError(RuntimeError):
    pass


def _run(args: list[str], repo_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        capture_output=True, text=True,
    )


def git_pull(repo_dir: Path) -> None:
    """Fetch and rebase onto the latest remote state.

    On conflict (e.g. two machines claimed the same line at once), aborts
    the rebase so the repo is left clean for the next attempt, rather than
    stuck mid-rebase.
    """
    proc = _run(["pull", "--rebase"], repo_dir)
    if proc.returncode != 0:
        _run(["rebase", "--abort"], repo_dir)
        raise QueueSyncError(f"git pull --rebase failed (aborted): {proc.stderr.strip()}")


def git_commit_push(repo_dir: Path, message: str, retries: int = 3) -> bool:
    """Commit any pending changes to totranslate.txt and push.

    Returns False if there was nothing to commit and nothing already
    committed-but-unpushed (e.g. left over from a previous call whose push
    exhausted its retries). Retries pull+push on rejection (another machine
    pushed first) up to `retries` times, using `git pull --rebase` between
    attempts so a concurrent claim/result from elsewhere is never silently
    clobbered.
    """
    add = _run(["add", "totranslate.txt"], repo_dir)
    if add.returncode != 0:
        raise QueueSyncError(f"git add failed: {add.stderr.strip()}")

    staged = _run(["diff", "--cached", "--quiet"], repo_dir)
    if staged.returncode != 0:  # something staged
        commit = _run(["commit", "-m", message], repo_dir)
        if commit.returncode != 0:
            raise QueueSyncError(f"git commit failed: {commit.stderr.strip()}")

    # Whether or not we just committed, there may already be earlier
    # unpushed commits (e.g. a prior call whose push exhausted its retries)
    # — always check against the upstream rather than only pushing when we
    # ourselves just committed, or a stranded commit would never get retried.
    ahead = _run(["rev-list", "--count", "@{u}..HEAD"], repo_dir)
    if ahead.returncode == 0 and ahead.stdout.strip() == "0":
        return False  # nothing to push

    for attempt in range(1, retries + 1):
        push = _run(["push"], repo_dir)
        if push.returncode == 0:
            return True
        if attempt == retries:
            raise QueueSyncError(f"git push failed after {retries} attempts: {push.stderr.strip()}")
        time.sleep(1.5 * attempt)
        git_pull(repo_dir)  # rebase local commit onto the remote's newer state, then retry push

    return True


def git_reset_hard_to_remote(repo_dir: Path, branch: str = "main") -> None:
    """Discard any local commits/changes and reset to the remote branch.

    Use this to recover after a claim genuinely conflicts with another
    machine's claim on the same line (git_pull's rebase failed and was
    aborted, or git_commit_push exhausted its retries) — the failed local
    attempt is discarded so the repo is clean for picking a different line.
    """
    fetch = _run(["fetch", "origin", branch], repo_dir)
    if fetch.returncode != 0:
        raise QueueSyncError(f"git fetch failed: {fetch.stderr.strip()}")
    reset = _run(["reset", "--hard", f"origin/{branch}"], repo_dir)
    if reset.returncode != 0:
        raise QueueSyncError(f"git reset --hard failed: {reset.stderr.strip()}")
