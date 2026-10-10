"""PANNs-compatible SemanticProvider adapter (weights optional / out of Git).

Implements a Cnn14 inference path derived from the audited MIT
``qiuqiangkong/audioset_tagging_cnn`` reference. Torch and model weights are
optional: absence yields a truthful unavailable state. The model-enabled path
never fabricates embeddings or hard-coded labels.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from koffer.analysis.cnn14 import (
    CNN14_EMBEDDING_DIM,
    CNN14_SAMPLE_RATE_HZ,
    load_audioset_class_labels,
    load_cnn14_checkpoint,
    run_cnn14_forward,
    waveform_from_audio_path,
)
from koffer.analysis.manifest import (
    ModelManifest,
    load_model_manifest,
    resolve_model_artifact_path,
    verify_model_artifact,
)
from koffer.analysis.semantic import SemanticInferenceResult, SemanticLabel
from koffer.domain.errors import UnsupportedOperationError, ValidationError

__all__ = [
    "PannsSemanticProvider",
    "PANNS_PROVIDER_ID",
]

PANNS_PROVIDER_ID = "panns"

# Optional DI hook for focused tests: (waveform, class_labels, top_k) -> result.
InferenceRunner = Callable[
    [np.ndarray, tuple[str, ...], int],
    tuple[list[tuple[str, float]], np.ndarray],
]


class PannsSemanticProvider:
    """Local PANNs Cnn14 adapter. Unavailable when weights/torch are missing."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        manifest: ModelManifest | None = None,
        artifact_path: Path | None = None,
        enabled: bool = True,
        top_k: int = 10,
        inference_runner: InferenceRunner | None = None,
        model: Any | None = None,
        class_labels: tuple[str, ...] | None = None,
        require_torch: bool = True,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._manifest = manifest if manifest is not None else load_model_manifest()
        self._artifact_path = (
            Path(artifact_path)
            if artifact_path is not None
            else resolve_model_artifact_path(self._cache_dir, self._manifest)
        )
        self._enabled = enabled
        self._top_k = top_k
        self._inference_runner = inference_runner
        self._model = model
        self._class_labels = class_labels
        self._require_torch = require_torch
        self._torch_checked = False
        self._torch_available = False

    @property
    def provider_id(self) -> str:
        return PANNS_PROVIDER_ID

    @property
    def model_version(self) -> str:
        return self._manifest.model_version

    @property
    def embedding_dim(self) -> int:
        return self._manifest.embedding_dim

    @property
    def artifact_path(self) -> Path:
        return self._artifact_path

    @property
    def manifest(self) -> ModelManifest:
        return self._manifest

    def is_available(self) -> bool:
        return self.unavailable_reason() is None

    def unavailable_reason(self) -> str | None:
        if not self._enabled:
            return "Semantic provider is disabled"
        if not self._artifact_path.is_file():
            return (
                "Semantic model weights are not installed. "
                "Install from Settings / model setup when ready."
            )
        if not self._manifest.checksum_recorded:
            return "Model manifest SHA256 is not recorded; refusing to load weights"
        try:
            verify_model_artifact(self._artifact_path, self._manifest)
        except ValidationError as exc:
            return f"Model artifact failed checksum verification: {exc.summary}"
        if self._inference_runner is not None:
            # Test/injected runner still requires a verified artifact, not torch.
            return None
        if self._require_torch and not self._ensure_torch():
            return "Optional dependency 'torch' is not installed"
        return None

    def infer(self, audio_path: Path) -> SemanticInferenceResult:
        reason = self.unavailable_reason()
        if reason is not None:
            raise UnsupportedOperationError(
                "Semantic model is unavailable",
                detail=reason,
            )
        path = Path(audio_path)
        if not path.is_file():
            raise ValidationError("Audio path is not a readable file", detail=str(path))

        waveform = waveform_from_audio_path(path, sample_rate_hz=CNN14_SAMPLE_RATE_HZ)
        labels_table = self._labels()
        if self._inference_runner is not None:
            pairs, embedding = self._inference_runner(waveform, labels_table, self._top_k)
        else:
            model = self._ensure_model()
            pairs, embedding = run_cnn14_forward(
                model,
                waveform,
                class_labels=labels_table,
                top_k=self._top_k,
                sample_rate_hz=CNN14_SAMPLE_RATE_HZ,
            )

        if embedding.dtype != np.float32 or embedding.ndim != 1:
            embedding = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if embedding.shape[0] != self.embedding_dim and embedding.shape[0] != CNN14_EMBEDDING_DIM:
            raise ValidationError(
                "Semantic embedding dimension mismatch",
                detail=f"expected={self.embedding_dim} actual={embedding.shape[0]}",
            )
        if not pairs:
            raise ValidationError("Semantic inference returned no labels")

        semantic_labels = tuple(
            SemanticLabel(label=name, score=float(score)) for name, score in pairs
        )
        return SemanticInferenceResult(
            labels=semantic_labels,
            embedding=embedding.astype(np.float32),
            model_version=self.model_version,
            provider=self.provider_id,
        )

    def _labels(self) -> tuple[str, ...]:
        if self._class_labels is not None:
            return self._class_labels
        self._class_labels = load_audioset_class_labels()
        return self._class_labels

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        self._model = load_cnn14_checkpoint(
            self._artifact_path,
            classes_num=len(self._labels()),
        )
        return self._model

    def _ensure_torch(self) -> bool:
        if self._torch_checked:
            return self._torch_available
        self._torch_checked = True
        try:
            import torch  # noqa: F401
        except ImportError:
            self._torch_available = False
            return False
        self._torch_available = True
        return True
