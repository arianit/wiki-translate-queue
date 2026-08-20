# wiki-translate-queue

Shared queue of Wikipedia articles to translate, plus their processing
status. This repo is *just* the shared state — no translation logic lives
here. It exists so that translation scripts running on different machines
can all find and safely update the same queue.

## `totranslate.txt` format

One Wikipedia article per line (URL or title). Lines starting with `#` are
ignored (comments / explanations). After a run, a processed line gets
`\tDONE`, `\tFAILED`, or `\tIN_PROGRESS\t<hostname>` appended. A consumer
picks the first line with no status mark. Add new articles anywhere below
the header; order doesn't matter beyond that.

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
# ... parse totranslate.txt, pick the first unmarked line ...

# 2. claim it before doing any slow work, so two machines can't pick
#    the same line
#    (write "\tIN_PROGRESS\t<hostname>" to that line)
claimed = queue_lib.git_commit_push(repo_dir, f"claim: {url}")
# If push kept failing after retries, queue_lib raises QueueSyncError.
# In that case: pull again, re-check the line you wanted — if someone
# else's IN_PROGRESS marker got there first, pick a different line.

# 3. do the (possibly slow) translation work

# 4. overwrite the IN_PROGRESS marker with DONE/FAILED, then:
queue_lib.git_commit_push(repo_dir, f"result: {url} -> DONE")
```

`queue_lib.git_commit_push()` already retries pull+push a few times on
rejection, so a normal race between two machines resolves on its own.

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
