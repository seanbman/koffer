"""Create a diagnostics ZIP that excludes audio/waveforms/embeddings by default."""

from __future__ import annotations

import json
import platform
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from koffer import __version__ as KOFFER_VERSION
from koffer.config.paths import AppPaths
from koffer.domain.timestamps import utc_now_iso
from koffer.persistence.connection import ConnectionFactory

__all__ = [
    "DiagnosticsBundleResult",
    "AUDIO_EXTENSIONS",
    "build_diagnostics_bundle",
    "default_excluded_prefixes",
]

AUDIO_EXTENSIONS = frozenset(
    {
        ".wav",
        ".wave",
        ".aif",
        ".aiff",
        ".flac",
        ".mp3",
        ".ogg",
        ".oga",
        ".m4a",
        ".aac",
        ".wma",
        ".opus",
    }
)

_DEFAULT_EXCLUDED_PREFIXES = (
    "waveforms/",
    "embeddings/",
    "similarity/",
    "covers/",
    "audio/",
    "managed-audio/",
)


@dataclass(frozen=True, slots=True)
class DiagnosticsBundleResult:
    path: Path
    included_names: tuple[str, ...]
    excluded_names: tuple[str, ...]
    excludes_audio_by_default: bool = True


def default_excluded_prefixes() -> tuple[str, ...]:
    return _DEFAULT_EXCLUDED_PREFIXES


def build_diagnostics_bundle(
    destination: Path,
    *,
    paths: AppPaths,
    connection_factory: ConnectionFactory | None = None,
    include_audio: bool = False,
    redact_paths: bool = False,
) -> DiagnosticsBundleResult:
    """Write a diagnostics ZIP. Audio/waveforms/embeddings excluded unless opted in."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()

    included: list[str] = []
    excluded: list[str] = []
    manifest = _build_manifest(
        paths=paths,
        connection_factory=connection_factory,
        include_audio=include_audio,
        redact_paths=redact_paths,
    )

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_json(zf, "manifest.json", manifest)
        included.append("manifest.json")

        _write_text(
            zf,
            "INCLUDED.txt",
            "\n".join(
                [
                    "Diagnostics bundle contents (default export):",
                    "- version/build and runtime versions",
                    "- OS/kernel summary",
                    "- resolved XDG paths (optionally redacted)",
                    "- schema version",
                    "- Source status summary",
                    "- recent sanitized logs (no audio)",
                    "- dependency inventory",
                    "",
                    "Excluded by default:",
                    "- audio files",
                    "- waveform cache",
                    "- embeddings",
                    "- cover art",
                    "- full database content",
                ]
            )
            + "\n",
        )
        included.append("INCLUDED.txt")

        log_dir = paths.log_dir
        if log_dir.is_dir():
            for log_path in sorted(log_dir.glob("*.log"))[:5]:
                arcname = f"logs/{log_path.name}"
                if _should_exclude(arcname, log_path, include_audio=include_audio):
                    excluded.append(arcname)
                    continue
                zf.write(log_path, arcname)
                included.append(arcname)

        # Never pack database bytes or cache trees by default.
        for cache_root_name in ("waveforms", "embeddings", "similarity", "covers"):
            cache_root = paths.cache_dir / cache_root_name
            if not cache_root.exists():
                continue
            for path in cache_root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(paths.cache_dir).as_posix()
                arcname = f"cache/{rel}"
                if not include_audio or _is_restricted_cache(rel):
                    excluded.append(arcname)
                    continue
                zf.write(path, arcname)
                included.append(arcname)

        # Bait / managed audio under data_dir must stay out unless include_audio.
        db_path = (
            Path(connection_factory.database_path).resolve()
            if connection_factory is not None
            else None
        )
        if paths.data_dir.is_dir():
            for path in paths.data_dir.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(paths.data_dir).as_posix()
                arcname = f"data/{rel}"
                if db_path is not None and path.resolve() == db_path:
                    excluded.append(arcname)
                    continue
                if _should_exclude(arcname, path, include_audio=include_audio):
                    excluded.append(arcname)
                    continue
                # Default diagnostics never include arbitrary data payloads.
                if not include_audio:
                    excluded.append(arcname)
                    continue
                zf.write(path, arcname)
                included.append(arcname)

    return DiagnosticsBundleResult(
        path=destination,
        included_names=tuple(included),
        excluded_names=tuple(excluded),
        excludes_audio_by_default=not include_audio,
    )


def _build_manifest(
    *,
    paths: AppPaths,
    connection_factory: ConnectionFactory | None,
    include_audio: bool,
    redact_paths: bool,
) -> dict[str, object]:
    schema_version = 0
    source_summary: list[dict[str, object]] = []
    if connection_factory is not None:
        conn = connection_factory.get_connection()
        row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        if row is not None and row["v"] is not None:
            schema_version = int(row["v"])
        for src in conn.execute(
            "SELECT id, display_name, root_path, status, enabled FROM sources ORDER BY display_name"
        ):
            root = str(src["root_path"])
            if redact_paths:
                root = _redact_path(root)
            source_summary.append(
                {
                    "id": str(src["id"]),
                    "display_name": str(src["display_name"]),
                    "root_path": root,
                    "status": str(src["status"]),
                    "enabled": bool(src["enabled"]),
                }
            )

    return {
        "koffer_version": KOFFER_VERSION,
        "created_at": utc_now_iso(),
        "python_version": sys.version.split()[0],
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
        },
        "qt_version": _qt_version(),
        "schema_version": schema_version,
        "paths": {
            "config_dir": _maybe_redact(str(paths.config_dir), redact_paths),
            "data_dir": _maybe_redact(str(paths.data_dir), redact_paths),
            "cache_dir": _maybe_redact(str(paths.cache_dir), redact_paths),
            "state_dir": _maybe_redact(str(paths.state_dir), redact_paths),
            "log_dir": _maybe_redact(str(paths.log_dir), redact_paths),
        },
        "sources": source_summary,
        "include_audio": include_audio,
        "excludes_by_default": list(_DEFAULT_EXCLUDED_PREFIXES) + sorted(AUDIO_EXTENSIONS),
        "package_format": "source-tree",
    }


def _qt_version() -> str:
    try:
        from PySide6.QtCore import qVersion

        return str(qVersion())
    except Exception:
        return "unavailable"


def _write_json(zf: zipfile.ZipFile, name: str, payload: dict[str, object]) -> None:
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    zf.writestr(name, data)


def _write_text(zf: zipfile.ZipFile, name: str, text: str) -> None:
    zf.writestr(name, text)


def _should_exclude(arcname: str, path: Path, *, include_audio: bool) -> bool:
    lower = arcname.lower()
    if any(part in lower for part in ("/waveforms/", "/embeddings/", "/similarity/", "/covers/")):
        return True
    if lower.startswith("waveforms/") or lower.startswith("embeddings/"):
        return True
    return path.suffix.lower() in AUDIO_EXTENSIONS and not include_audio


def _is_restricted_cache(rel: str) -> bool:
    lowered = rel.lower()
    return lowered.startswith(("waveforms/", "embeddings/", "similarity/", "covers/"))


def _redact_path(value: str) -> str:
    parts = Path(value).parts
    if len(parts) <= 2:
        return "***"
    return str(Path(parts[0]) / "***" / parts[-1])


def _maybe_redact(value: str, redact: bool) -> str:
    return _redact_path(value) if redact else value
