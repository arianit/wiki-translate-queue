# wiki-translate-queue

Shared queue of Wikipedia articles to translate, plus their processing
status. This repo is *just* the shared state — no translation logic lives
here. It exists so that translation scripts running on different machines
can all find and safely update the same queue.

## `totranslate.txt` format

One Wikipedia article per line (URL or title), followed by a single status
field: nothing (pending), `\tCLAIMED\t<hostname>\t<iso timestamp>` (picked
up but not finished — treated as abandoned and reclaimed if the timestamp
is more than a few hours old), or `\tDONE` / `\tFAILED` (finished). Lines
starting with `#` are comments. A consumer picks the first line with no
status field; new articles can be added anywhere below the header.

Status is always a *replacement* of the whole field after the URL, never
an append — e.g. going from `CLAIMED\t<host>\t<ts>` to `DONE` replaces that
entire suffix, it doesn't get appended after it.

## Protocol for consumer scripts

Multiple machines may run against this queue at the same time. Use
`queue_lib.py` (vendor a copy, or add this repo's clone to `sys.path` and
`import queue_lib`) — it does **not** rely on git merging divergent
history to resolve races: this file's lines are short, structurally
similar, and sit right next to each other, and git's line-based diff/merge
(rebase's patch-apply *and* a plain three-way merge) can group two
adjacent-but-unrelated edits into a single spurious conflict even when
nothing actually overlaps. So `git_pull()` is strictly fast-forward-only,
and any divergence — a genuine same-line race, or just a spuriously
"conflicting" adjacent edit — is resolved the same way: discard the local
attempt and redo it against a fresh pull, never merge.

The high-level functions already implement this discard-and-redo loop, so
most consumers only need two calls:

```python
from pathlib import Path
import queue_lib

repo_dir = Path("~/code/wiki-translate-queue").expanduser()

claimed = queue_lib.claim_next_pending(repo_dir)  # pulls, picks the first
                                                   # pending (or stale-
                                                   # CLAIMED) line, claims
                                                   # + pushes it, retrying
                                                   # against a fresh pull
                                                   # on any conflict
if claimed is None:
    ...  # nothing pending
line_no, url = claimed

# do the (possibly slow) translation work

queue_lib.finish_line(repo_dir, line_no, url, "DONE")  # or "FAILED",
                                                        # optionally reason=...
```

`finish_line()` and `claim_next_pending()` both retry internally (default
5 attempts) via the discard-and-redo pattern; they raise `QueueSyncError`
only if that's still failing after all attempts (e.g. no network).

Lower-level building blocks (`parse_queue`, `set_line_status`,
`claim_marker`, `is_stale_claim`, `git_pull`, `git_commit_push`,
`git_reset_hard_to_remote`, `sync_to_remote`) are there for a consumer
that needs custom selection logic instead of "first pending line" — see
`batch_controller.py` in `wikitranslateautorun` for a full worked example
(it has its own cost-based article ordering, so it claims a specific,
already-chosen line rather than using `claim_next_pending`).

## Current consumers

- `wikitranslateautorun`'s `batch_controller.py` — the nightly cron
  controller. Clones this repo locally and symlinks `totranslate.txt` into
  its working directory. Has its own cost-based article ordering, so it
  claims a specific, already-chosen line via the low-level building blocks
  rather than `claim_next_pending`.
- `translation-harness`'s `wiki-translate-harness queue` subcommand
  (`wiki_translate_harness/queue_runner.py`) — drains the queue via
  `claim_next_pending`/`finish_line`, translating each article with the
  same `run_pipeline()` its manual `--title`/`--titles`/`--category` modes
  use.
- `multimodeltranslationpipeline`'s `mmtp queue` subcommand
  (`mmtp/queue_runner.py`) — same pattern, calling `translate_article()`.

All three dynamically import `queue_lib.py` from a local clone of this
repo rather than vendoring a copy, so a fix here (like the merge-safety
rewrite in the commit history) only needs to land once.

## Not shared here

Per-machine caches (e.g. cost-estimate/state caches used purely to order
the queue) stay local to each consumer and are reconciled *from*
`totranslate.txt` — this file is the only source of truth for done/failed
status.
