"""GitHub command-file transport: payloads are data, never extra commands.

Filesystem checks protect inputs and bundle artifacts from accidental aliasing.
They are not a sandbox against a hostile external writer changing directories.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import stat
from collections.abc import Iterable, Mapping

from .errors import GateConfigError
from .outputs import LOCK_NAME, _validate_destinations

_VARIABLES = ('GITHUB_OUTPUT', 'GITHUB_STEP_SUMMARY')
_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*\Z')


def validate_command_files(report_paths: Iterable[str] = ()) -> dict:
    paths = [Path(os.path.abspath(path)) for path in report_paths]
    for variable in _VARIABLES:
        value = os.environ.get(variable)
        if value:
            path = Path(os.path.abspath(value))
            if path.name == LOCK_NAME:
                raise GateConfigError(f'{variable} cannot use the publication lock filename')
            paths.append(path)
    try:
        return _validate_destinations(paths)
    except OSError as exc:
        raise GateConfigError('GitHub command-file destination could not be inspected') from exc


def _append(variable: str, content: str, report_paths: Iterable[str]) -> None:
    value = os.environ.get(variable)
    if not value:
        return
    path = Path(os.path.abspath(value))
    report_paths = tuple(report_paths)
    try:
        payload = content.encode('utf-8')
    except UnicodeError as exc:
        raise GateConfigError('GitHub command content must be valid UTF-8') from exc
    validate_command_files(report_paths)
    fd = None
    try:
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
        flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0)
        fd = os.open(path, flags, 0o600)
        actual = os.fstat(fd)
        if not stat.S_ISREG(actual.st_mode):
            raise GateConfigError('GitHub command file must be regular')
        states = validate_command_files(report_paths)
        current = states[path]
        if current is None or (actual.st_dev, actual.st_ino) != (current.st_dev, current.st_ino):
            raise GateConfigError('GitHub command-file destination changed during opening')
        with os.fdopen(fd, 'ab') as fh:
            fd = None
            fh.write(payload)
    except (OSError, ValueError) as exc:
        raise GateConfigError(f'{variable} command file could not be written') from exc
    finally:
        if fd is not None:
            os.close(fd)


def emit_outputs(pairs: Mapping[str, object], report_paths: Iterable[str] = ()) -> None:
    if not os.environ.get('GITHUB_OUTPUT'):
        return
    lines = []
    for name, raw in pairs.items():
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise GateConfigError('GitHub output names must be simple identifiers')
        value = str(raw)
        if '\x00' in value:
            raise GateConfigError('GitHub output values cannot contain NUL')
        if '\n' in value or '\r' in value:
            # Inspect the complete value before choosing a delimiter, including
            # CRLF and lone-CR boundaries. No probabilistic collision assumption.
            occupied = set(value.splitlines())
            index = 0
            delimiter = f'lrg_output_{index}'
            while delimiter in occupied:
                index += 1
                delimiter = f'lrg_output_{index}'
            lines.append(f'{name}<<{delimiter}\n{value}\n{delimiter}\n')
        else:
            lines.append(f'{name}={value}\n')
    _append('GITHUB_OUTPUT', ''.join(lines), report_paths)


def emit_summary(markdown: str, report_paths: Iterable[str] = ()) -> None:
    _append('GITHUB_STEP_SUMMARY', markdown + '\n', report_paths)
