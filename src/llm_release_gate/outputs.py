"""Stage complete evidence before publishing; protect inputs and prior artifacts.

Per-file replacement is atomic. Caught publication failures roll back the named
bundle, but a process crash or an uncooperative external writer is not a filesystem
transaction. A lock serializes cooperating CLI writers to the same directory.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import stat
import tempfile
from collections.abc import Mapping

from .errors import GateConfigError
from .loading import loaded_input_sources

LOCK_NAME = '.llm-release-gate.lock'


def _identity(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def _validate_destinations(paths: list[Path]) -> dict[Path, os.stat_result | None]:
    states = {}
    sources = loaded_input_sources()
    for path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError:
            info = None
        for source_path, device, inode in sources:
            if _identity(path) == source_path or (
                info is not None and inode and (info.st_dev, info.st_ino) == (device, inode)
            ):
                raise GateConfigError(f'output would replace a loaded input: {path}')
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise GateConfigError(f'output must be a regular file, not a link or special file: {path}')
        for other, other_info in states.items():
            if _identity(path) == _identity(other) or (
                info is not None and other_info is not None and info.st_ino
                and (info.st_dev, info.st_ino) == (other_info.st_dev, other_info.st_ino)
            ):
                raise GateConfigError(f'output destinations alias each other: {path} and {other}')
        states[path] = info
    return states


def _signature(info: os.stat_result | None) -> tuple | None:
    if info is None:
        return None
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode)


def publish_documents(documents: Mapping[str, str]) -> None:
    """Publish named UTF-8 documents in one directory with recoverable rollback.

    Validate and encode everything before touching an existing file. Refuse
    symlink/special-file outputs and aliases to any JSON source read in this CLI
    invocation, including transitive replay fixtures. Unrelated files are untouched.
    New files are private (0600); replacements retain existing permission bits.
    """
    if not documents:
        return
    paths = [Path(os.path.abspath(path)) for path in documents]
    if len(set(paths)) != len(paths) or len({path.parent for path in paths}) != 1:
        raise GateConfigError('output documents require distinct paths in one directory')
    if any(path.name == LOCK_NAME for path in paths):
        raise GateConfigError('output name is reserved for the publication lock')
    # Encoding/rendering failures must precede any publication or backup work.
    encoded = [content.encode('utf-8') for content in documents.values()]
    parent = paths[0].parent
    stage: Path | None = None
    keep_recovery = False
    locked = False
    lock = parent / LOCK_NAME
    try:
        _validate_destinations(paths)
        parent.mkdir(parents=True, exist_ok=True)
        try:
            with lock.open('x', encoding='utf-8') as fh:
                locked = True
                fh.write(f'pid={os.getpid()}\n')
        except FileExistsError as exc:
            raise GateConfigError(f'output publication lock already exists: {lock}; '
                                  'check for an active writer before removing a stale lock') from exc
        states = _validate_destinations(paths)
        stage = Path(tempfile.mkdtemp(prefix='.lrg-stage-', dir=parent))
        originals: dict[Path, Path | None] = {}
        for index, (path, content) in enumerate(zip(paths, encoded)):
            new = stage / f'new-{index}'
            new.write_bytes(content)
            info = states[path]
            new.chmod(stat.S_IMODE(info.st_mode) if info else 0o600)
            if info is None:
                originals[path] = None
            else:
                backup = stage / f'old-{index}'
                shutil.copyfile(path, backup)
                backup.chmod(stat.S_IMODE(info.st_mode))
                originals[path] = backup
        (stage / 'recovery.json').write_text(json.dumps({
            'files': [{'destination': str(path),
                       'backup': originals[path].name if originals[path] else None}
                      for path in paths],
        }, indent=2) + '\n', encoding='utf-8')
        current = _validate_destinations(paths)
        if any(_signature(current[path]) != _signature(states[path]) for path in paths):
            raise GateConfigError('output destination changed while staging; publication refused')
        committed = []
        try:
            for index, path in enumerate(paths):
                os.replace(stage / f'new-{index}', path)
                committed.append(path)
        except OSError as exc:
            failed_rollback = []
            for path in reversed(committed):
                try:
                    backup = originals[path]
                    if backup is None:
                        path.unlink()
                    else:
                        os.replace(backup, path)
                except OSError:
                    failed_rollback.append(path)
            if failed_rollback:
                keep_recovery = True
                raise GateConfigError(f'output publication failed and rollback was incomplete; '
                                      f'recovery files retained at {stage}') from exc
            raise GateConfigError('output publication failed; previous files restored') from exc
    except OSError as exc:
        raise GateConfigError(f'output could not be published in {parent}: {exc}') from exc
    finally:
        # Never remove another writer's lock, nor destroy evidence needed after a
        # failed rollback. Residual lock/staging files make a crash visible.
        if stage is not None and not keep_recovery:
            shutil.rmtree(stage)
        if locked and not keep_recovery:
            lock.unlink()
