"""SemanticProvider contract + Fake provider for CI (docs/19, docs/20)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from koffer.analysis.manifest import ModelManifest, load_model_manifest

__all__ = [
    "SemanticLabel",
    "SemanticInferenceResult",
    "SemanticProvider",
    "FakeSemanticProvider",
    "map_panns_labels",
    "load_label_map",
]


@dataclass(frozen=True, slots=True)
class SemanticLabel:
    """One provider label with raw score (not product confidence)."""

    label: str
    score: float


@dataclass(frozen=True, slots=True)
class SemanticInferenceResult:
    """Tagging + embedding output from a SemanticProvider."""

    labels: tuple[SemanticLabel, ...]
    embedding: np.ndarray
    model_version: str
    provider: str

    def __post_init__(self) -> None:
        if self.embedding.dtype != np.float32:
            object.__setattr__(self, "embedding", np.asarray(self.embedding, dtype=np.float32))
        if self.embedding.ndim != 1:
            raise ValueError("embedding must be a 1-D float32 vector")


@runtime_checkable
class SemanticProvider(Protocol):
    """Local semantic inference adapter (PANNs-compatible in V1)."""

    @property
    def provider_id(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    @property
    def embedding_dim(self) -> int: ...

    def is_available(self) -> bool: ...

    def unavailable_reason(self) -> str | None: ...

    def infer(self, audio_path: Path) -> SemanticInferenceResult: ...


class FakeSemanticProvider:
    """Deterministic CI provider: no torch, no downloads, always available."""

    def __init__(
        self,
        *,
        model_version: str = "fake-v1",
        embedding_dim: int = 32,
        provider_id: str = "fake",
    ) -> None:
        if embedding_dim < 8:
            raise ValueError("embedding_dim must be >= 8")
        self._model_version = model_version
        self._embedding_dim = embedding_dim
        self._provider_id = provider_id

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def infer(self, audio_path: Path) -> SemanticInferenceResult:
        path = Path(audio_path)
        digest = hashlib.sha256(path.name.encode("utf-8")).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
        raw = rng.standard_normal(self._embedding_dim).astype(np.float32)
        norm = float(np.linalg.norm(raw))
        embedding = (raw / norm) if norm > 0 else raw
        stem = path.stem.lower()
        labels: list[SemanticLabel] = []
        if "kick" in stem or "bassdrum" in stem:
            labels.append(SemanticLabel("Bass drum", 0.91))
        elif "snare" in stem:
            labels.append(SemanticLabel("Snare drum", 0.88))
        elif "hat" in stem or "hihat" in stem:
            labels.append(SemanticLabel("Hi-hat", 0.86))
        else:
            labels.append(SemanticLabel("Synthesizer", 0.55))
        return SemanticInferenceResult(
            labels=tuple(labels),
            embedding=embedding.astype(np.float32),
            model_version=self._model_version,
            provider=self._provider_id,
        )


def load_label_map(path: Path | None = None) -> dict[str, dict[str, str]]:
    """Load AudioSet/PANNs -> Koffer taxonomy mappings."""
    import json
    from importlib import resources

    if path is not None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    else:
        root = resources.files("koffer.analysis.label_maps")
        traversable = root.joinpath("panns_v1.json")
        with resources.as_file(traversable) as mapped:
            payload = json.loads(Path(mapped).read_text(encoding="utf-8"))
    mappings = payload.get("mappings", {})
    if not isinstance(mappings, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for label, target in mappings.items():
        if isinstance(target, dict) and "dimension" in target and "value" in target:
            result[str(label)] = {
                "dimension": str(target["dimension"]),
                "value": str(target["value"]),
            }
    return result


def map_panns_labels(
    labels: tuple[SemanticLabel, ...] | list[SemanticLabel],
    *,
    label_map: dict[str, dict[str, str]] | None = None,
) -> list[tuple[str, str, float]]:
    """Map provider labels to taxonomy triples ``(dimension, value, score)``."""
    mapping = label_map if label_map is not None else load_label_map()
    mapped: list[tuple[str, str, float]] = []
    for item in labels:
        target = mapping.get(item.label)
        if target is None:
            continue
        mapped.append((target["dimension"], target["value"], float(item.score)))
    return mapped


def disabled_provider_from_manifest(
    manifest: ModelManifest | None = None,
) -> FakeSemanticProvider:
    """Helper retained for tests that want manifest-aligned dims with a fake."""
    loaded = manifest if manifest is not None else load_model_manifest()
    return FakeSemanticProvider(
        model_version=f"fake-{loaded.version}",
        embedding_dim=min(64, loaded.embedding_dim),
        provider_id="fake",
    )
