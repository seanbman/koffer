"""SemanticProvider contract tests — no weight downloads."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from koffer.analysis.panns import PannsSemanticProvider
from koffer.analysis.semantic import FakeSemanticProvider, SemanticProvider, map_panns_labels
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.errors import UnsupportedOperationError


def test_fake_provider_satisfies_protocol_and_is_deterministic(tmp_path: Path) -> None:
    provider: SemanticProvider = FakeSemanticProvider(embedding_dim=32)
    assert provider.is_available() is True
    wav = write_sine_wav(tmp_path / "kick_oneshot.wav", duration_s=0.1)
    first = provider.infer(wav)
    second = provider.infer(wav)
    assert first.embedding.shape == (32,)
    assert first.embedding.dtype == np.float32
    assert np.allclose(first.embedding, second.embedding)
    assert any(label.label == "Bass drum" for label in first.labels)
    mapped = map_panns_labels(first.labels)
    assert ("instrument_source", "Kick", 0.91) in mapped


def test_panns_provider_unavailable_without_weights(tmp_path: Path) -> None:
    provider = PannsSemanticProvider(tmp_path / "cache")
    assert provider.is_available() is False
    assert provider.unavailable_reason() is not None
    wav = write_sine_wav(tmp_path / "tone.wav", duration_s=0.1)
    try:
        provider.infer(wav)
        raise AssertionError("expected UnsupportedOperationError")
    except UnsupportedOperationError as exc:
        assert exc.code == "unsupported_operation"


def test_panns_provider_has_no_fabricated_fallback_embedding() -> None:
    # Historical placeholder helpers must not exist on the model-enabled path.
    assert not hasattr(PannsSemanticProvider, "_fallback_embedding")
