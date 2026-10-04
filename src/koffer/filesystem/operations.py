"""Safe copy/move primitives: temp+verify+atomic rename; no silent overwrite."""

from __future__ import annotations

import contextlib
import os
import uuid
from pathlib import Path

from koffer.filesystem.hashing import content_fingerprint


def path_fingerprint(path: Path) -> str:
    """Stable size+mtime fingerprint for plan staleness checks."""
    resolved = Path(path)
    stat = resolved.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def keep_both_destination(destination: Path) -> Path:
    """Generate ``name (N).ext`` that does not yet exist (docs/28)."""
    parent = destination.parent
    stem = destination.stem
    suffix = destination.suffix
    index = 2
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def same_filesystem(source: Path, destination_parent: Path) -> bool:
    """True when source and destination directory share a device id."""
    return source.stat().st_dev == destination_parent.stat().st_dev


def verified_copy(source: Path, destination: Path, *, overwrite: bool = False) -> str:
    """Copy via temp sibling, verify SHA-256, then atomic rename into place.

    Never silently overwrites an existing destination when ``overwrite`` is False.
    Returns the destination content hash (must match source).
    """
    src = Path(source)
    dst = Path(destination)
    if not src.is_file():
        msg = f"source is not a readable file: {src}"
        raise FileNotFoundError(msg)
    if dst.exists() and not overwrite:
        msg = f"destination already exists: {dst}"
        raise FileExistsError(msg)

    dst.parent.mkdir(parents=True, exist_ok=True)
    source_hash = content_fingerprint(src)
    source_size = src.stat().st_size
    temp_name = f".{dst.name}.koffer-tmp-{uuid.uuid4().hex}"
    temp_path = dst.parent / temp_name

    try:
        with src.open("rb") as src_handle, temp_path.open("wb") as tmp_handle:
            while True:
                chunk = src_handle.read(1024 * 1024)
                if not chunk:
                    break
                tmp_handle.write(chunk)
            tmp_handle.flush()
            os.fsync(tmp_handle.fileno())

        temp_size = temp_path.stat().st_size
        if temp_size != source_size:
            msg = f"copy size mismatch: expected {source_size}, got {temp_size}"
            raise OSError(msg)
        temp_hash = content_fingerprint(temp_path)
        if temp_hash != source_hash:
            msg = "copy hash mismatch before finalize"
            raise OSError(msg)

        if dst.exists() and overwrite:
            # Explicit replace only: remove destination then rename temp into place.
            dst.unlink()
        # os.rename fails if destination exists on POSIX — never silent overwrite.
        os.rename(temp_path, dst)
    except Exception:
        if temp_path.exists():
            with contextlib.suppress(OSError):
                temp_path.unlink()
        raise

    final_hash = content_fingerprint(dst)
    if final_hash != source_hash:
        msg = "destination hash mismatch after finalize"
        raise OSError(msg)
    return final_hash


def verified_move(source: Path, destination: Path, *, overwrite: bool = False) -> str:
    """Move file: same-FS rename when possible; else verified-copy-then-delete.

    Source is deleted only after destination verification succeeds.
    Returns destination content hash.
    """
    src = Path(source)
    dst = Path(destination)
    if not src.is_file():
        msg = f"source is not a readable file: {src}"
        raise FileNotFoundError(msg)
    if dst.exists() and not overwrite:
        msg = f"destination already exists: {dst}"
        raise FileExistsError(msg)

    dst.parent.mkdir(parents=True, exist_ok=True)
    source_hash = content_fingerprint(src)

    if same_filesystem(src, dst.parent):
        if dst.exists() and overwrite:
            dst.unlink()
        os.rename(src, dst)
        final_hash = content_fingerprint(dst)
        if final_hash != source_hash:
            msg = "move hash mismatch after same-filesystem rename"
            raise OSError(msg)
        return final_hash

    # Cross-filesystem: verified copy, then delete source only after success.
    final_hash = verified_copy(src, dst, overwrite=overwrite)
    if final_hash != source_hash:
        msg = "cross-filesystem move hash mismatch; source retained"
        raise OSError(msg)
    try:
        src.unlink()
    except OSError as exc:
        # Destination is good; report incomplete move without pretending clean.
        raise OSError(f"destination verified but source delete failed: {src}") from exc
    if src.exists():
        msg = f"source still present after delete: {src}"
        raise OSError(msg)
    return final_hash
