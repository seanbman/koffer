"""Recursive Source scanner with exclusions and supported-extension filtering."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from koffer.domain.enums import ExclusionPatternType
from koffer.domain.models import ExclusionRule
from koffer.filesystem.extensions import is_supported_audio_extension, normalize_extension

# Common OS trash / recycle metadata directory names (basename match).
_DEFAULT_TRASH_DIR_NAMES = frozenset(
    {
        ".trash",
        ".trashes",
        "$recycle.bin",
        "recycle.bin",
    }
)


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """One supported audio file discovered under a Source root."""

    relative_path: str
    absolute_path: Path
    filename: str
    extension: str
    size_bytes: int
    mtime_ns: int
    device_id: int | None
    inode: int | None


class EnumerationFailed(Exception):
    """Source root could not be enumerated; do not mass-mark Samples missing."""

    def __init__(
        self,
        message: str,
        *,
        offline: bool = False,
        permission_denied: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.offline = offline
        self.permission_denied = permission_denied


def normalize_relative_path(relative_path: str) -> str:
    """Normalize to forward-slash relative path without leading './'."""
    cleaned = relative_path.replace("\\", "/").strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.lstrip("/")


def _path_has_hidden_component(relative_path: str) -> bool:
    parts = [part for part in normalize_relative_path(relative_path).split("/") if part]
    return any(part.startswith(".") for part in parts)


def matches_exclusion(relative_path: str, rules: Sequence[ExclusionRule]) -> bool:
    """Return True when any enabled rule excludes the relative path."""
    rel = normalize_relative_path(relative_path)
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.pattern_type is ExclusionPatternType.HIDDEN_POLICY:
            if _path_has_hidden_component(rel):
                return True
            continue
        if rule.pattern_type is ExclusionPatternType.RELATIVE_PATH:
            pattern = normalize_relative_path(rule.pattern)
            if rel == pattern or rel.startswith(pattern.rstrip("/") + "/"):
                return True
            continue
        if rule.pattern_type is ExclusionPatternType.GLOB:
            pattern_lower = rule.pattern.lower()
            if fnmatch.fnmatch(rel, rule.pattern) or fnmatch.fnmatch(rel.lower(), pattern_lower):
                return True
            # Also allow basename-only globs.
            basename = rel.rsplit("/", 1)[-1]
            if fnmatch.fnmatch(basename, rule.pattern) or fnmatch.fnmatch(
                basename.lower(), pattern_lower
            ):
                return True
    return False


def _is_trash_dirname(name: str) -> bool:
    return name.lower() in _DEFAULT_TRASH_DIR_NAMES


def enumerate_audio_files(
    root: Path,
    *,
    recursive: bool = True,
    rules: Sequence[ExclusionRule] = (),
) -> list[DiscoveredFile]:
    """Walk ``root`` and return supported audio files after applying exclusions.

    Raises:
        EnumerationFailed: when the root is missing, not a directory, or not
            readable. Callers must not mark all Samples missing in that case.
    """
    try:
        root_resolved = root.expanduser().resolve(strict=False)
    except OSError as exc:
        raise EnumerationFailed(
            f"cannot resolve Source root: {root}",
            offline=True,
        ) from exc

    if not root_resolved.exists():
        raise EnumerationFailed(
            f"Source root does not exist: {root_resolved}",
            offline=True,
        )
    if not root_resolved.is_dir():
        raise EnumerationFailed(
            f"Source root is not a directory: {root_resolved}",
            offline=True,
        )
    if not os.access(root_resolved, os.R_OK | os.X_OK):
        raise EnumerationFailed(
            f"Source root is not readable: {root_resolved}",
            permission_denied=True,
        )

    discovered: list[DiscoveredFile] = []
    try:
        if recursive:
            # Subdirectory listdir failures are skipped (not whole-Source offline).
            walker = os.walk(
                root_resolved,
                topdown=True,
                onerror=None,
                followlinks=False,
            )
            for dirpath, dirnames, filenames in walker:
                current = Path(dirpath)
                # Prune excluded / trash / hidden dirs in-place for os.walk.
                keep: list[str] = []
                for dirname in dirnames:
                    child_rel = normalize_relative_path(
                        str((current / dirname).relative_to(root_resolved))
                    )
                    if _is_trash_dirname(dirname):
                        continue
                    if matches_exclusion(child_rel, rules) or matches_exclusion(
                        child_rel + "/", rules
                    ):
                        continue
                    keep.append(dirname)
                dirnames[:] = keep

                for filename in filenames:
                    absolute = current / filename
                    relative = normalize_relative_path(str(absolute.relative_to(root_resolved)))
                    if matches_exclusion(relative, rules):
                        continue
                    if not is_supported_audio_extension(filename):
                        continue
                    discovered.append(_stat_discovered(absolute, relative, filename))
        else:
            for entry in root_resolved.iterdir():
                if not entry.is_file():
                    continue
                relative = normalize_relative_path(entry.name)
                if matches_exclusion(relative, rules):
                    continue
                if not is_supported_audio_extension(entry.name):
                    continue
                discovered.append(_stat_discovered(entry, relative, entry.name))
    except EnumerationFailed:
        raise
    except PermissionError as exc:
        raise EnumerationFailed(
            f"permission denied while enumerating {root_resolved}",
            permission_denied=True,
        ) from exc
    except OSError as exc:
        raise EnumerationFailed(
            f"enumeration failed for {root_resolved}: {exc}",
            offline=True,
        ) from exc

    discovered.sort(key=lambda item: item.relative_path)
    return discovered


def preview_exclusions(
    root: Path,
    rules: Sequence[ExclusionRule],
    *,
    recursive: bool = True,
) -> tuple[tuple[str, ...], int]:
    """Return (matched_relative_paths, included_supported_count) for a dry-run."""
    # Enumerate without rules, then classify.
    try:
        all_supported = enumerate_audio_files(root, recursive=recursive, rules=())
    except EnumerationFailed:
        return (), 0

    matched: list[str] = []
    included = 0
    for item in all_supported:
        if matches_exclusion(item.relative_path, rules):
            matched.append(item.relative_path)
        else:
            included += 1
    return tuple(matched), included


def _stat_discovered(absolute: Path, relative: str, filename: str) -> DiscoveredFile:
    try:
        stat = absolute.stat(follow_symlinks=False)
    except OSError as exc:
        raise EnumerationFailed(
            f"stat failed for {absolute}: {exc}",
            offline=True,
        ) from exc
    device_id: int | None
    inode: int | None
    try:
        device_id = int(stat.st_dev)
        inode = int(stat.st_ino)
    except (AttributeError, OverflowError, ValueError):
        device_id = None
        inode = None
    return DiscoveredFile(
        relative_path=relative,
        absolute_path=absolute,
        filename=filename,
        extension=normalize_extension(filename),
        size_bytes=int(stat.st_size),
        mtime_ns=int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
        device_id=device_id,
        inode=inode,
    )
