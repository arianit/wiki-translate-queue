"""Shared git sync helpers for consumers of this repo's totranslate.txt.

Any translation script, on any machine, that wants to read or update the
shared queue should follow this discipline:

    claim_next_pending(repo_dir)   # pull, pick a pending line, claim + push it
    ... do the (possibly slow) translation work ...
    finish_line(repo_dir, ...)     # replace CLAIMED with DONE/FAILED, push

Both are safe under concurrent use from multiple machines, but NOT by
merging divergent git history — git's line-based diff/merge can group two
*adjacent but unrelated* line edits into a single conflicting hunk (this
file's entries are short, structurally similar, and sit right next to each
other, which triggers this far more than it would in typical text). So
this module never merges: git_pull() is a strict fast-forward, and any
divergence is handled by discarding the local attempt
(git_reset_hard_to_remote) and redoing the specific edit against the fresh
remote state — never by asking git to reconcile two versions of the file.
"""
from __future__ import annotations

import datetime
import socket
import subprocess
from pathlib import Path

QUEUE_FILENAME = "totranslate.txt"
DEFAULT_STALE_CLAIM_HOURS = 3.0


class QueueSyncError(RuntimeError):
    pass


def _run(args: list[str], repo_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        capture_output=True, text=True,
    )


def git_pull(repo_dir: Path) -> None:
    """Fast-forward onto the latest remote state. Raises QueueSyncError if
    that's not possible (local has diverged, e.g. a stray unpushed commit
    from a prior crashed run) — callers should git_reset_hard_to_remote()
    and redo their edit rather than have this attempt any merge."""
    proc = _run(["pull", "--ff-only"], repo_dir)
    if proc.returncode != 0:
        raise QueueSyncError(f"git pull --ff-only failed: {proc.stderr.strip()}")


def git_commit_push(repo_dir: Path, message: str) -> bool:
    """Commit whatever's currently changed in totranslate.txt and push.

    Single-shot: raises QueueSyncError immediately on any failure,
    including push rejection (another machine pushed first). Does not
    retry internally — callers (claim_next_pending / finish_line) recover
    by discarding this attempt (git_reset_hard_to_remote) and redoing the
    whole read-modify-write cycle against a fresh pull, which is the only
    reliable way to resolve a divergence on this file (see module
    docstring for why merging is unsafe here).

    Returns False if there was nothing to commit and nothing already
    committed-but-unpushed.
    """
    add = _run(["add", QUEUE_FILENAME], repo_dir)
    if add.returncode != 0:
        raise QueueSyncError(f"git add failed: {add.stderr.strip()}")

    staged = _run(["diff", "--cached", "--quiet"], repo_dir)
    if staged.returncode != 0:  # something staged
        commit = _run(["commit", "-m", message], repo_dir)
        if commit.returncode != 0:
            raise QueueSyncError(f"git commit failed: {commit.stderr.strip()}")

    # Whether or not we just committed, there may already be an earlier
    # unpushed commit (e.g. a prior call that got reset elsewhere but this
    # checkout still has it) — always check against upstream rather than
    # only pushing when we ourselves just committed.
    ahead = _run(["rev-list", "--count", "@{u}..HEAD"], repo_dir)
    if ahead.returncode == 0 and ahead.stdout.strip() == "0":
        return False  # nothing to push

    push = _run(["push"], repo_dir)
    if push.returncode != 0:
        raise QueueSyncError(f"git push rejected: {push.stderr.strip()}")
    return True


def git_reset_hard_to_remote(repo_dir: Path, branch: str = "main") -> None:
    """Discard any local commits/changes and reset to the remote branch.

    This is the recovery step after any QueueSyncError: it discards
    whatever this checkout attempted, leaving it byte-identical to the
    remote so the next attempt starts from a known-good state rather than
    trying to reconcile divergent history.
    """
    fetch = _run(["fetch", "origin", branch], repo_dir)
    if fetch.returncode != 0:
        raise QueueSyncError(f"git fetch failed: {fetch.stderr.strip()}")
    reset = _run(["reset", "--hard", f"origin/{branch}"], repo_dir)
    if reset.returncode != 0:
        raise QueueSyncError(f"git reset --hard failed: {reset.stderr.strip()}")


def sync_to_remote(repo_dir: Path) -> None:
    """Get this checkout to exactly match the remote, recovering from any
    local divergence. Use at the start of a run before reading the queue."""
    try:
        git_pull(repo_dir)
    except QueueSyncError:
        git_reset_hard_to_remote(repo_dir)


# --------------------------------------------------------------------------
# Queue-file protocol: parsing, claiming, and finishing lines.
#
# Format: one article per line, `#`-comments/blank lines ignored. The field
# after the URL (tab-separated) is empty (pending), "CLAIMED\t<hostname>\t
# <iso timestamp>" (picked up but not finished), or "DONE" / "FAILED". A
# status is always a *replacement* of that whole field, never an append.
# --------------------------------------------------------------------------

def parse_queue(repo_dir: Path) -> list[tuple[int, str, str | None, list[str]]]:
    """Returns [(line_no, url, status, extra_fields)] for every non-blank,
    non-comment line. extra_fields holds whatever tab fields follow status
    (e.g. CLAIMED's hostname + claim timestamp)."""
    queue_path = repo_dir / QUEUE_FILENAME
    out = []
    if not queue_path.exists():
        return out
    for i, raw in enumerate(queue_path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = raw.rstrip("\n").split("\t")
        url = parts[0].strip()
        status = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        extra = [p.strip() for p in parts[2:]]
        if url:
            out.append((i, url, status, extra))
    return out


def set_line_status(repo_dir: Path, line_no: int, status_suffix: str) -> None:
    """Replace whatever status suffix (if any) currently follows the URL on
    this line with status_suffix (e.g. "DONE", or
    "CLAIMED\\t<hostname>\\t<iso timestamp>")."""
    queue_path = repo_dir / QUEUE_FILENAME
    lines = queue_path.read_text().splitlines(keepends=True)
    raw = lines[line_no - 1].rstrip("\n")
    url = raw.split("\t", 1)[0]
    lines[line_no - 1] = f"{url}\t{status_suffix}\n"
    queue_path.write_text("".join(lines))


def claim_marker(hostname: str | None = None) -> str:
    host = hostname or socket.gethostname()
    return f"CLAIMED\t{host}\t{datetime.datetime.now().astimezone().isoformat()}"


def is_stale_claim(extra: list[str], stale_hours: float = DEFAULT_STALE_CLAIM_HOURS) -> bool:
    """True if a CLAIMED line's timestamp is missing/unparseable or older
    than stale_hours — i.e. whoever claimed it likely crashed before
    finishing, so it should be treated as abandoned and reclaimed."""
    if len(extra) < 2:
        return True
    try:
        claimed_at = datetime.datetime.fromisoformat(extra[1])
    except ValueError:
        return True
    return datetime.datetime.now().astimezone() - claimed_at > datetime.timedelta(hours=stale_hours)


def claim_next_pending(
    repo_dir: Path,
    stale_hours: float = DEFAULT_STALE_CLAIM_HOURS,
    max_attempts: int = 5,
) -> tuple[int, str] | None:
    """Finds the first pending (or stale-CLAIMED) line, claims it, and
    pushes the claim. On any conflict, discards the attempt and redoes the
    whole pick-and-claim against a fresh pull (which may yield the same or
    a different line, depending on what the other side changed). Returns
    (line_no, url), or None if there's nothing pending.
    """
    for _ in range(max_attempts):
        sync_to_remote(repo_dir)
        candidate = None
        for line_no, url, status, extra in parse_queue(repo_dir):
            if status is None or (status == "CLAIMED" and is_stale_claim(extra, stale_hours)):
                candidate = (line_no, url)
                break
        if candidate is None:
            return None
        line_no, url = candidate
        set_line_status(repo_dir, line_no, claim_marker())
        try:
            git_commit_push(repo_dir, f"claim: line {line_no} {url}")
            return line_no, url
        except QueueSyncError:
            continue  # sync_to_remote() at the top of the next loop cleans up
    return None


def finish_line(
    repo_dir: Path,
    line_no: int,
    url: str,
    status: str,
    reason: str | None = None,
    max_attempts: int = 5,
) -> None:
    """Replaces a claimed line's status with a final DONE/FAILED and
    pushes, redoing the edit against a fresh pull if it conflicts with
    something else that changed in the meantime. Raises QueueSyncError if
    it still can't get through after max_attempts — the result only
    exists in this checkout's working tree at that point, so callers
    should log and treat it as needing manual attention (a re-run of the
    consumer will simply retry the whole claim, since the line is still
    CLAIMED under this same run's marker in that case).
    """
    for attempt in range(1, max_attempts + 1):
        set_line_status(repo_dir, line_no, status)
        if reason:
            queue_path = repo_dir / QUEUE_FILENAME
            lines = queue_path.read_text().splitlines(keepends=True)
            lines.insert(line_no, f"# reason: {reason}\n")
            queue_path.write_text("".join(lines))
        try:
            git_commit_push(repo_dir, f"result: line {line_no} {url} -> {status}")
            return
        except QueueSyncError:
            if attempt == max_attempts:
                raise
            sync_to_remote(repo_dir)
