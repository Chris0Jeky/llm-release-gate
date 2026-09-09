#!/usr/bin/env python3
"""Reconstruct and optionally extract the llm-release-gate acceleration bundle."""

from __future__ import annotations

import argparse
import base64
import hashlib
import lzma
import tarfile
from pathlib import Path

EXPECTED_SHA256 = "9963e49e1c2368cb47df9f639a7f24dbd9fce6d64b0a455130c99323f64ebc89"
EXPECTED_BYTES = 63304
ARCHIVE_NAME = "llm-release-gate-acceleration-bundle.tar.xz"


def safe_extract(archive: Path, destination: Path, *, force: bool) -> None:
    if destination.exists() and any(destination.iterdir()) and not force:
        raise SystemExit(
            f"refusing to extract into non-empty {destination}; pass --force or choose --destination"
        )
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, mode="r:xz") as tf:
        for member in tf.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise SystemExit(f"unsafe archive member: {member.name}")
        tf.extractall(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract", action="store_true", help="extract after reconstruction")
    parser.add_argument("--destination", type=Path, default=Path("reconstructed-bundle"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    parts = sorted(here.glob("bundle.tar.xz.b64.part-*"))
    if len(parts) != 9:
        raise SystemExit(f"expected 9 archive shards, found {len(parts)}")

    encoded = b"".join(part.read_bytes() for part in parts)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise SystemExit(f"invalid base64 shards: {exc}") from exc

    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != EXPECTED_BYTES or digest != EXPECTED_SHA256:
        raise SystemExit(
            f"archive verification failed: bytes={len(payload)}, sha256={digest}"
        )

    try:
        lzma.decompress(payload)
    except lzma.LZMAError as exc:
        raise SystemExit(f"archive is not valid xz data: {exc}") from exc

    archive = here / ARCHIVE_NAME
    archive.write_bytes(payload)
    print(f"wrote {archive} ({len(payload)} bytes, sha256={digest})")

    if args.extract:
        safe_extract(archive, args.destination, force=args.force)
        print(f"extracted into {args.destination.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
