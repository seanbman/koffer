"""Model manifest schema + checksum verification hooks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koffer.analysis.manifest import (
    check_model_manifest,
    load_model_manifest,
    sha256_file,
    verify_model_artifact,
)
from koffer.domain.errors import ValidationError


def test_packaged_manifest_loads_and_check_succeeds_without_weights() -> None:
    manifest = load_model_manifest()
    assert manifest.provider == "panns"
    assert manifest.model == "Cnn14"
    assert manifest.embedding_dim == 2048
    result = check_model_manifest(cache_dir=Path("/tmp/koffer-no-models-cache"))
    assert result.ok is True
    assert result.artifact_present is False


def test_verify_model_artifact_checks_sha256(tmp_path: Path) -> None:
    payload = b"fake-weight-bytes"
    artifact = tmp_path / "Cnn14_mAP=0.431.pth"
    artifact.write_bytes(payload)
    digest = sha256_file(artifact)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "panns",
                "model": "Cnn14",
                "sample_rate_hz": 32000,
                "artifact": artifact.name,
                "version": "test-v1",
                "source_url": "https://example.invalid/model.pth",
                "sha256": digest,
                "size_bytes": len(payload),
                "embedding_dim": 8,
                "license_note": "test",
            }
        ),
        encoding="utf-8",
    )
    manifest = load_model_manifest(manifest_path)
    verify_model_artifact(artifact, manifest)

    artifact.write_bytes(b"tampered")
    with pytest.raises(ValidationError, match="checksum mismatch"):
        verify_model_artifact(artifact, manifest)


def test_verify_refuses_unrecorded_checksum(tmp_path: Path) -> None:
    artifact = tmp_path / "model.pth"
    artifact.write_bytes(b"x")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "panns",
                "model": "Cnn14",
                "sample_rate_hz": 32000,
                "artifact": "model.pth",
                "version": "pending",
                "source_url": "https://example.invalid/model.pth",
                "sha256": "",
                "size_bytes": 0,
                "embedding_dim": 8,
                "license_note": "test",
            }
        ),
        encoding="utf-8",
    )
    manifest = load_model_manifest(manifest_path)
    with pytest.raises(ValidationError, match="not recorded"):
        verify_model_artifact(artifact, manifest)
