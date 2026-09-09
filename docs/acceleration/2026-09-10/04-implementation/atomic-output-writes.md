# Atomic output writes and deterministic size limits

## Objective

A crash or disk error must not leave a mixture of old and new report files that appear to belong to one gate invocation.

## Single-file primitive

```python
import os
import tempfile
from pathlib import Path


def atomic_write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
```

## Multi-file publication

A set of independent `os.replace` operations is not transactionally atomic. Safer options:

1. write all artifacts into a new unique run directory, then atomically update a small `latest` pointer/manifest;
2. write files plus a final `COMPLETE` marker and teach consumers to ignore directories without it;
3. publish content-addressed directories keyed by `result_hash` and never overwrite them.

The third option aligns best with reproducibility. A human-friendly output path can point or copy to the immutable run directory after completion.

## Size policy

- deterministic public/private/local profiles define per-field and total size limits;
- truncate human renderings, not the canonical evidence used for scoring;
- include original and retained byte/count metadata;
- reject snapshots exceeding configured safety limits before exhausting memory;
- stream large JSONL evidence in a later triggered feature rather than loading it speculatively now.

## Tests

- injected failure after each artifact write;
- existing output preserved after failed replacement;
- no temporary files remain after handled failure;
- concurrent writers target distinct result-hash directories;
- Windows `os.replace` behaviour with closed file handles;
- deterministic truncation at multibyte Unicode boundaries;
- disk-full/permission error returns exit 2 and never reports a successful publication.
