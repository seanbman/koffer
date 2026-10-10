"""Explicit semantic model artifact installation (docs/23, docs/32).

Downloads or copies are never implicit during inference. Writes are atomic:
temp sibling → checksum/size verify → rename. Cancel/failure leaves no partial
trusted artifact at the destination path.
"""

from __future__ import annotations

import contextlib
import os
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from koffer.analysis.manifest import (
    ModelManifest,
    resolve_model_artifact_path,
    sha256_file,
    verify_model_artifact,
)
from koffer.domain.errors import ValidationError

__all__ = [
    "InstallProgress",
    "install_model_artifact",
    "ModelInstallCancelled",
]

_CHUNK_SIZE = 1024 * 1024


class ModelInstallCancelled(ValidationError):
    """User cancelled model installation before a trusted artifact was finalized."""

    def __init__(self, detail: str = "") -> None:
        super().__init__("Model installation cancelled", detail=detail)


@dataclass(frozen=True, slots=True)
class InstallProgress:
    """Coarse install progress for Settings UI wiring (next Order)."""

    bytes_done: int
    bytes_total: int | None
    stage: str


ProgressCallback = Callable[[InstallProgress], None]
CancelCheck = Callable[[], bool]


def install_model_artifact(
    cache_dir: Path,
    *,
    manifest: ModelManifest | None = None,
    source: Path | str | None = None,
    overwrite: bool = False,
    cancel_check: CancelCheck | None = None,
    progress: ProgressCallback | None = None,
) -> Path:
    """Install a verified model artifact into the provider cache location.

    ``source`` may be a local file path or an http(s) URL. When omitted, the
    manifest ``source_url`` is used. Inference never calls this helper.
    """
    from koffer.analysis.manifest import load_model_manifest

    loaded = manifest if manifest is not None else load_model_manifest()
    if not loaded.checksum_recorded:
        raise ValidationError(
            "Model manifest SHA256 is not recorded; refusing to install",
            detail=loaded.version,
        )

    destination = resolve_model_artifact_path(Path(cache_dir), loaded)
    if destination.is_file() and not overwrite:
        verify_model_artifact(destination, loaded)
        size = destination.stat().st_size
        _emit(progress, InstallProgress(size, size, "ready"))
        return destination

    source_ref: Path | str = loaded.source_url if source is None else source

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name = f".{destination.name}.koffer-install-{uuid.uuid4().hex}"
    temp_path = destination.parent / temp_name

    try:
        _emit(progress, InstallProgress(0, None, "downloading"))
        if isinstance(source_ref, Path) or (
            isinstance(source_ref, str) and Path(source_ref).is_file()
        ):
            local = Path(source_ref)
            _copy_local(local, temp_path, cancel_check=cancel_check, progress=progress)
        else:
            _download_url(
                str(source_ref),
                temp_path,
                cancel_check=cancel_check,
                progress=progress,
                expected_size=loaded.size_bytes if loaded.size_bytes > 0 else None,
            )

        _emit(
            progress,
            InstallProgress(temp_path.stat().st_size, temp_path.stat().st_size, "verifying"),
        )
        if cancel_check is not None and cancel_check():
            raise ModelInstallCancelled("cancelled before checksum verification")
        verify_model_artifact(temp_path, loaded)

        _emit(
            progress,
            InstallProgress(temp_path.stat().st_size, temp_path.stat().st_size, "finalizing"),
        )
        if cancel_check is not None and cancel_check():
            raise ModelInstallCancelled("cancelled before finalize")

        if destination.exists():
            if not overwrite:
                raise ValidationError(
                    "Model artifact destination already exists",
                    detail=str(destination),
                )
            destination.unlink()
        os.rename(temp_path, destination)
        # Re-verify the trusted path so a rename race cannot leave bad bytes.
        verify_model_artifact(destination, loaded)
        _emit(
            progress,
            InstallProgress(destination.stat().st_size, destination.stat().st_size, "ready"),
        )
        return destination
    except Exception:
        if temp_path.exists():
            with contextlib.suppress(OSError):
                temp_path.unlink()
        # Never leave a partial file under the trusted destination name.
        if destination.is_file():
            try:
                verify_model_artifact(destination, loaded)
            except ValidationError:
                with contextlib.suppress(OSError):
                    destination.unlink()
        raise


def _emit(progress: ProgressCallback | None, event: InstallProgress) -> None:
    if progress is not None:
        progress(event)


def _copy_local(
    source: Path,
    temp_path: Path,
    *,
    cancel_check: CancelCheck | None,
    progress: ProgressCallback | None,
) -> None:
    if not source.is_file():
        raise ValidationError("Install source is not a readable file", detail=str(source))
    total = source.stat().st_size
    done = 0
    with source.open("rb") as src, temp_path.open("wb") as dst:
        while True:
            if cancel_check is not None and cancel_check():
                raise ModelInstallCancelled("cancelled during local copy")
            chunk = src.read(_CHUNK_SIZE)
            if not chunk:
                break
            dst.write(chunk)
            done += len(chunk)
            _emit(progress, InstallProgress(done, total, "downloading"))
        dst.flush()
        os.fsync(dst.fileno())


def _download_url(
    url: str,
    temp_path: Path,
    *,
    cancel_check: CancelCheck | None,
    progress: ProgressCallback | None,
    expected_size: int | None,
) -> None:
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValidationError("Model install URL must be http(s)", detail=url)
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 — explicit URL install
            total_header = response.headers.get("Content-Length")
            total: int | None = (
                int(total_header) if total_header and total_header.isdigit() else expected_size
            )
            done = 0
            with temp_path.open("wb") as dst:
                while True:
                    if cancel_check is not None and cancel_check():
                        raise ModelInstallCancelled("cancelled during download")
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
                    done += len(chunk)
                    _emit(progress, InstallProgress(done, total, "downloading"))
                dst.flush()
                os.fsync(dst.fileno())
    except ModelInstallCancelled:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValidationError(
            "Failed to download model artifact",
            detail=f"{url}: {exc}",
        ) from exc

    # Size hint from manifest when Content-Length was absent.
    if expected_size is not None and expected_size > 0:
        actual = temp_path.stat().st_size
        if actual != expected_size:
            raise ValidationError(
                "Downloaded model artifact size mismatch",
                detail=f"expected={expected_size} actual={actual}",
            )
    # Cheap existence check; full sha256 happens in caller.
    _ = sha256_file(temp_path)
