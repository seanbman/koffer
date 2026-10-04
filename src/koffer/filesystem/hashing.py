"""Content fingerprint helpers for cache keys and change detection."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 1024 * 1024


def content_fingerprint(path: Path) -> str:
    """Return a hex SHA-256 of file bytes. Read-only; never mutates ``path``."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
