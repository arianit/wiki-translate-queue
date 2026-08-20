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

Multiple machines may run against this queue at the same time, so treat
`git push` rejection as expected, not an error: it means someone else
updated the queue first. Use `queue_lib.py` (vendor a copy, or add this
repo's clone to `sys.path` and `import queue_lib`):

```python
from pathlib import Path
import queue_lib

repo_dir = Path("~/code/wiki-translate-queue").expanduser()

queue_lib.git_pull(repo_dir)                 # 1. get the latest state
# ... parse totranslate.txt, pick the first line with no status field
#     (treat a CLAIMED line whose timestamp is stale — a few hours old —
#     as pending too, in case whoever claimed it crashed) ...

# 2. claim it before doing any slow work, so two machines can't pick the
#    same line: replace the line's status field with
#    "CLAIMED\t<hostname>\t<iso timestamp>"
try:
    queue_lib.git_commit_push(repo_dir, f"claim: {url}")
except queue_lib.QueueSyncError:
    # Someone else claimed a conflicting version of this line first.
    queue_lib.git_reset_hard_to_remote(repo_dir)
    # pull again, re-parse, pick a different line, retry.

# 3. do the (possibly slow) translation work

# 4. replace the CLAIMED status field with DONE or FAILED, then:
queue_lib.git_commit_push(repo_dir, f"result: {url} -> DONE")
```

`queue_lib.git_commit_push()` already retries pull+push a few times on
rejection, so a normal race between two machines resolves on its own —
`git_reset_hard_to_remote()` is only needed for the harder case where the
retries themselves are exhausted or the rebase hits a real conflict.
See `batch_controller.py` in `wikitranslateautorun` for a full worked
example (`claim_line`, `set_line_status`, and the retry/reset handling
around it).

## Current consumers

- [`wikitranslateautorun`](https://github.com/arianit) `batch_controller.py`
  — the nightly cron controller. Clones this repo locally and symlinks
  `totranslate.txt` into its working directory.
- `translation-harness` / `multimodeltranslationpipeline` — not wired up
  yet, but should follow the same protocol via `queue_lib.py` rather than
  reinventing it, when they're ready to consume this queue.

## Not shared here

Per-machine caches (e.g. cost-estimate/state caches used purely to order
the queue) stay local to each consumer and are reconciled *from*
`totranslate.txt` — this file is the only source of truth for done/failed
status.
