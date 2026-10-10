"""PANNs Cnn14 inference path — no production weight download."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from koffer.analysis.cnn14 import (
    CNN14_CLASSES_NUM,
    CNN14_EMBEDDING_DIM,
    load_audioset_class_labels,
    run_cnn14_forward,
)
from koffer.analysis.manifest import ModelManifest, load_model_manifest, sha256_file
from koffer.analysis.model_install import ModelInstallCancelled, install_model_artifact
from koffer.analysis.panns import PannsSemanticProvider
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.errors import UnsupportedOperationError, ValidationError


def _fixture_manifest(
    tmp_path: Path, artifact: Path, *, embedding_dim: int = 2048
) -> ModelManifest:
    digest = sha256_file(artifact)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "panns",
                "model": "Cnn14",
                "sample_rate_hz": 32000,
                "artifact": artifact.name,
                "version": "fixture-cnn14",
                "source_url": "https://example.invalid/Cnn14_fixture.pth",
                "sha256": digest,
                "size_bytes": artifact.stat().st_size,
                "embedding_dim": embedding_dim,
                "license_note": "test fixture",
            }
        ),
        encoding="utf-8",
    )
    return load_model_manifest(manifest_path)


def test_audioset_labels_table_is_complete() -> None:
    labels = load_audioset_class_labels()
    assert len(labels) == CNN14_CLASSES_NUM
    assert "Bass drum" in labels
    assert "Synthesizer" in labels


def test_panns_unavailable_without_weights_or_torch(tmp_path: Path) -> None:
    provider = PannsSemanticProvider(tmp_path / "cache")
    assert provider.is_available() is False
    reason = provider.unavailable_reason()
    assert reason is not None
    wav = write_sine_wav(tmp_path / "tone.wav", duration_s=0.05)
    with pytest.raises(UnsupportedOperationError):
        provider.infer(wav)


def test_panns_rejects_checksum_mismatch(tmp_path: Path) -> None:
    artifact = tmp_path / "Cnn14_fixture.pth"
    artifact.write_bytes(b"good-bytes")
    manifest = _fixture_manifest(tmp_path, artifact)
    artifact.write_bytes(b"tampered-bytes")
    provider = PannsSemanticProvider(
        tmp_path / "cache",
        manifest=manifest,
        artifact_path=artifact,
        inference_runner=lambda *_args: ([("Bass drum", 0.9)], np.ones(2048, dtype=np.float32)),
    )
    assert provider.is_available() is False
    assert "checksum" in (provider.unavailable_reason() or "").lower()


def test_panns_executes_cnn14_forward_via_torch_boundary(tmp_path: Path) -> None:
    """Acceptance: verified fixture + torch boundary runs a real forward-shaped pass."""
    artifact = tmp_path / "Cnn14_fixture.pth"
    artifact.write_bytes(b"verified-cnn14-fixture-bytes")
    manifest = _fixture_manifest(tmp_path, artifact)
    labels = load_audioset_class_labels()
    forward_calls: list[object] = []

    class _FakeTensor:
        def __init__(self, array: np.ndarray) -> None:
            self._array = array

        def detach(self) -> _FakeTensor:
            return self

        def cpu(self) -> _FakeTensor:
            return self

        def numpy(self) -> np.ndarray:
            return self._array

    class _FakeCnn14:
        training = False

        def eval(self) -> None:
            return None

        def train(self) -> None:
            return None

        def __call__(self, logmel: object) -> dict[str, _FakeTensor]:
            forward_calls.append(logmel)
            clipwise = np.zeros(CNN14_CLASSES_NUM, dtype=np.float32)
            bass_idx = labels.index("Bass drum")
            clipwise[bass_idx] = 0.93
            clipwise[labels.index("Music")] = 0.40
            embedding = np.linspace(0.01, 1.0, CNN14_EMBEDDING_DIM, dtype=np.float32)
            return {
                "clipwise_output": _FakeTensor(clipwise[np.newaxis, :]),
                "embedding": _FakeTensor(embedding[np.newaxis, :]),
            }

    # Patch torch boundary used by run_cnn14_forward without requiring a torch install.
    import koffer.analysis.cnn14 as cnn14_mod

    class _FakeNoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    class _FakeTorch:
        @staticmethod
        def from_numpy(array: np.ndarray) -> object:
            return array

        @staticmethod
        def no_grad() -> _FakeNoGrad:
            return _FakeNoGrad()

    original_import = cnn14_mod._import_torch
    cnn14_mod._import_torch = lambda: _FakeTorch()  # type: ignore[assignment]
    try:
        provider = PannsSemanticProvider(
            tmp_path / "cache",
            manifest=manifest,
            artifact_path=artifact,
            model=_FakeCnn14(),
            class_labels=labels,
            require_torch=False,
        )
        assert provider.is_available() is True
        wav = write_sine_wav(tmp_path / "kick.wav", duration_s=0.2, sample_rate=32000)
        result = provider.infer(wav)
    finally:
        cnn14_mod._import_torch = original_import  # type: ignore[assignment]

    assert forward_calls, "Cnn14 forward must be invoked"
    assert result.embedding.shape == (CNN14_EMBEDDING_DIM,)
    assert result.embedding.dtype == np.float32
    assert abs(float(np.linalg.norm(result.embedding)) - 1.0) < 1e-5
    assert result.labels[0].label == "Bass drum"
    assert result.labels[0].score == pytest.approx(0.93)
    # Must not be the old fabricated Synthesizer/0.5 placeholder.
    assert not (
        len(result.labels) == 1
        and result.labels[0].label == "Synthesizer"
        and abs(result.labels[0].score - 0.5) < 1e-9
    )


def test_inference_runner_boundary_never_returns_fabricated_placeholder(tmp_path: Path) -> None:
    artifact = tmp_path / "Cnn14_fixture.pth"
    artifact.write_bytes(b"fixture")
    manifest = _fixture_manifest(tmp_path, artifact)
    called = {"n": 0}

    def runner(
        waveform: np.ndarray,
        class_labels: tuple[str, ...],
        top_k: int,
    ) -> tuple[list[tuple[str, float]], np.ndarray]:
        called["n"] += 1
        assert waveform.ndim == 1
        assert len(class_labels) == CNN14_CLASSES_NUM
        emb = np.zeros(2048, dtype=np.float32)
        emb[3] = 2.0
        return [("Hi-hat", 0.88), ("Music", 0.2)], emb

    provider = PannsSemanticProvider(
        tmp_path / "cache",
        manifest=manifest,
        artifact_path=artifact,
        inference_runner=runner,
    )
    wav = write_sine_wav(tmp_path / "hat.wav", duration_s=0.1)
    result = provider.infer(wav)
    assert called["n"] == 1
    assert result.labels[0].label == "Hi-hat"
    assert result.embedding.shape == (2048,)


def test_install_model_artifact_atomic_checksum_and_cancel(tmp_path: Path) -> None:
    source = tmp_path / "source.pth"
    source.write_bytes(b"official-style-weights-bytes")
    digest = sha256_file(source)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "provider": "panns",
                "model": "Cnn14",
                "sample_rate_hz": 32000,
                "artifact": "Cnn14_mAP=0.431.pth",
                "version": "install-test",
                "source_url": "https://example.invalid/model.pth",
                "sha256": digest,
                "size_bytes": source.stat().st_size,
                "embedding_dim": 2048,
                "license_note": "test",
            }
        ),
        encoding="utf-8",
    )
    manifest = load_model_manifest(manifest_path)
    cache = tmp_path / "cache"

    installed = install_model_artifact(cache, manifest=manifest, source=source)
    assert installed.is_file()
    assert sha256_file(installed) == digest
    assert not any(cache.rglob(".*.koffer-install-*"))

    # Cancel during copy leaves no trusted artifact for a fresh destination.
    cache2 = tmp_path / "cache2"
    cancel_after = {"n": 0}

    def cancel_check() -> bool:
        cancel_after["n"] += 1
        return cancel_after["n"] > 1

    with pytest.raises(ModelInstallCancelled):
        install_model_artifact(
            cache2,
            manifest=manifest,
            source=source,
            cancel_check=cancel_check,
        )
    dest = cache2 / "models" / manifest.provider / manifest.version / manifest.artifact
    assert not dest.exists()
    assert not any(cache2.rglob(".*.koffer-install-*"))

    # Checksum failure rejects and leaves no trusted artifact.
    bad = tmp_path / "bad.pth"
    bad.write_bytes(b"wrong-bytes")
    cache3 = tmp_path / "cache3"
    with pytest.raises(ValidationError, match="checksum"):
        install_model_artifact(cache3, manifest=manifest, source=bad)
    dest3 = cache3 / "models" / manifest.provider / manifest.version / manifest.artifact
    assert not dest3.exists()


def test_frame_waveform_pads_short_and_truncates_long_without_source_mutation(
    tmp_path: Path,
) -> None:
    from koffer.analysis.cnn14 import (
        CNN14_MAX_SAMPLES,
        CNN14_MIN_FRAMES,
        CNN14_MIN_SAMPLES,
        frame_waveform_for_cnn14,
        logmel_from_waveform,
    )

    short = np.linspace(-0.2, 0.2, 8000, dtype=np.float32)  # 0.25 s @ 32 kHz
    framed_short = frame_waveform_for_cnn14(short)
    assert framed_short.shape == (CNN14_MIN_SAMPLES,)
    assert np.array_equal(framed_short[: short.size], short)
    assert np.all(framed_short[short.size :] == 0.0)
    # Original buffer untouched.
    assert short.shape == (8000,)
    assert short.dtype == np.float32

    mel = logmel_from_waveform(short)
    assert mel.shape[2] >= CNN14_MIN_FRAMES

    long = np.ones(CNN14_MAX_SAMPLES + 5000, dtype=np.float32)
    framed_long = frame_waveform_for_cnn14(long)
    assert framed_long.shape == (CNN14_MAX_SAMPLES,)
    assert long.shape == (CNN14_MAX_SAMPLES + 5000,)

    wav = write_sine_wav(tmp_path / "oneshot.wav", duration_s=0.25, sample_rate=32000)
    before = wav.read_bytes()
    from koffer.analysis.cnn14 import waveform_from_audio_path

    decoded = waveform_from_audio_path(wav)
    framed = frame_waveform_for_cnn14(decoded)
    assert framed.shape == (CNN14_MIN_SAMPLES,)
    assert wav.read_bytes() == before


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("torch") is None,
    reason="torch optional; real checkpoint exercise when semantic extra installed",
)
def test_real_torch_cnn14_forward_with_generated_checkpoint(tmp_path: Path) -> None:
    import torch

    from koffer.analysis.cnn14 import build_cnn14, load_cnn14_checkpoint

    model = build_cnn14()
    artifact = tmp_path / "Cnn14_generated.pth"
    torch.save({"model": model.state_dict()}, artifact)
    manifest = _fixture_manifest(tmp_path, artifact)
    loaded = load_cnn14_checkpoint(artifact)
    labels = load_audioset_class_labels()
    wav = write_sine_wav(tmp_path / "tone.wav", duration_s=0.25, sample_rate=32000)
    source_before = wav.read_bytes()
    provider = PannsSemanticProvider(
        tmp_path / "cache",
        manifest=manifest,
        artifact_path=artifact,
        model=loaded,
        class_labels=labels,
    )
    result = provider.infer(wav)
    assert wav.read_bytes() == source_before
    assert result.embedding.shape == (CNN14_EMBEDDING_DIM,)
    assert result.embedding.dtype == np.float32
    assert abs(float(np.linalg.norm(result.embedding)) - 1.0) < 1e-5
    assert len(result.labels) == min(10, CNN14_CLASSES_NUM)
    # Full 527-class clipwise path is exercised; top-k is a view over it.
    from koffer.analysis.cnn14 import waveform_from_audio_path

    waveform = waveform_from_audio_path(wav)
    pairs, embedding = run_cnn14_forward(
        loaded, waveform, class_labels=labels, top_k=CNN14_CLASSES_NUM
    )
    assert len(pairs) == CNN14_CLASSES_NUM
    assert embedding.shape == (CNN14_EMBEDDING_DIM,)
    assert embedding.dtype == np.float32
    assert abs(float(np.linalg.norm(embedding)) - 1.0) < 1e-5
    assert pairs[0][0] == result.labels[0].label
    assert wav.read_bytes() == source_before
