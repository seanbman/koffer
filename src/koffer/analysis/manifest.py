"""Model manifest load + SHA256 verification hooks (docs/23).

Weights are never committed to Git. Manifests are checked in; artifacts live
under the XDG cache and are verified before use.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from koffer.domain.errors import ValidationError

__all__ = [
    "ModelManifest",
    "ManifestCheckResult",
    "default_panns_manifest_path",
    "load_model_manifest",
    "sha256_file",
    "verify_model_artifact",
    "check_model_manifest",
]

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ModelManifest:
    """Checked-in model identity and checksum policy."""

    provider: str
    model: str
    sample_rate_hz: int
    artifact: str
    version: str
    source_url: str
    sha256: str
    size_bytes: int
    embedding_dim: int
    license_note: str
    path: Path | None = None

    @property
    def model_version(self) -> str:
        return self.version

    @property
    def checksum_recorded(self) -> bool:
        return len(self.sha256) == 64 and all(c in "0123456789abcdef" for c in self.sha256)


@dataclass(frozen=True, slots=True)
class ManifestCheckResult:
    """Outcome of ``check_model_manifest`` (schema + optional artifact)."""

    ok: bool
    manifest: ModelManifest
    artifact_path: Path | None
    artifact_present: bool
    checksum_ok: bool | None
    messages: tuple[str, ...]


def default_panns_manifest_path() -> Path:
    """Return the packaged PANNs Cnn14 manifest path."""
    packaged = Path(__file__).resolve().parent / "models" / "panns_cnn14.json"
    if packaged.is_file():
        return packaged
    root = resources.files("koffer.analysis.models")
    traversable = root.joinpath("panns_cnn14.json")
    with resources.as_file(traversable) as path:
        return Path(path)


def load_model_manifest(path: Path | None = None) -> ModelManifest:
    """Load and validate a model manifest JSON document."""
    manifest_path = Path(path) if path is not None else default_panns_manifest_path()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            "Model manifest is unreadable",
            detail=f"{manifest_path}: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise ValidationError("Model manifest root must be an object")

    required = (
        "provider",
        "model",
        "sample_rate_hz",
        "artifact",
        "version",
        "source_url",
        "sha256",
        "size_bytes",
        "license_note",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValidationError(
            "Model manifest missing required fields",
            detail=", ".join(missing),
        )

    embedding_dim = payload.get("embedding_dim", 2048)
    try:
        return ModelManifest(
            provider=str(payload["provider"]),
            model=str(payload["model"]),
            sample_rate_hz=int(payload["sample_rate_hz"]),
            artifact=str(payload["artifact"]),
            version=str(payload["version"]),
            source_url=str(payload["source_url"]),
            sha256=str(payload["sha256"]).strip().lower(),
            size_bytes=int(payload["size_bytes"]),
            embedding_dim=int(embedding_dim),
            license_note=str(payload["license_note"]),
            path=manifest_path,
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Model manifest has invalid field types", detail=str(exc)) from exc


def sha256_file(path: Path) -> str:
    """Return lowercase hex SHA-256 of ``path`` bytes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_artifact(path: Path, manifest: ModelManifest) -> None:
    """Verify artifact bytes against the manifest checksum.

    Raises ``ValidationError`` when the checksum is missing/unrecorded or mismatched.
    """
    artifact = Path(path)
    if not artifact.is_file():
        raise ValidationError(
            "Model artifact is not a readable file",
            detail=str(artifact),
        )
    if not manifest.checksum_recorded:
        raise ValidationError(
            "Model manifest SHA256 is not recorded yet; refuse to trust artifact",
            detail=manifest.version,
        )
    actual = sha256_file(artifact)
    if actual != manifest.sha256:
        raise ValidationError(
            "Model artifact checksum mismatch",
            detail=f"expected={manifest.sha256} actual={actual}",
        )
    if manifest.size_bytes > 0:
        size = artifact.stat().st_size
        if size != manifest.size_bytes:
            raise ValidationError(
                "Model artifact size mismatch",
                detail=f"expected={manifest.size_bytes} actual={size}",
            )


def resolve_model_artifact_path(cache_dir: Path, manifest: ModelManifest) -> Path:
    """Canonical cache location for a model artifact (weights stay out of Git)."""
    return Path(cache_dir) / "models" / manifest.provider / manifest.version / manifest.artifact


def check_model_manifest(
    *,
    manifest_path: Path | None = None,
    cache_dir: Path | None = None,
    require_artifact: bool = False,
) -> ManifestCheckResult:
    """Validate manifest schema and optionally verify a cached artifact.

    Absence of weights is success unless ``require_artifact`` is true — the app
    must remain usable without the model.
    """
    manifest = load_model_manifest(manifest_path)
    messages: list[str] = [f"manifest ok: {manifest.provider}/{manifest.model}@{manifest.version}"]
    artifact_path: Path | None = None
    artifact_present = False
    checksum_ok: bool | None = None

    if not manifest.checksum_recorded:
        messages.append("sha256 not recorded yet (weights must not be trusted/bundled)")

    if cache_dir is not None:
        artifact_path = resolve_model_artifact_path(cache_dir, manifest)
        artifact_present = artifact_path.is_file()
        if artifact_present:
            try:
                verify_model_artifact(artifact_path, manifest)
                checksum_ok = True
                messages.append(f"artifact checksum ok: {artifact_path}")
            except ValidationError as exc:
                checksum_ok = False
                messages.append(f"artifact checksum failed: {exc.summary}")
                return ManifestCheckResult(
                    ok=False,
                    manifest=manifest,
                    artifact_path=artifact_path,
                    artifact_present=True,
                    checksum_ok=False,
                    messages=tuple(messages),
                )
        else:
            messages.append("artifact absent (app remains usable)")
            if require_artifact:
                return ManifestCheckResult(
                    ok=False,
                    manifest=manifest,
                    artifact_path=artifact_path,
                    artifact_present=False,
                    checksum_ok=None,
                    messages=tuple(messages),
                )

    return ManifestCheckResult(
        ok=True,
        manifest=manifest,
        artifact_path=artifact_path,
        artifact_present=artifact_present,
        checksum_ok=checksum_ok,
        messages=tuple(messages),
    )
