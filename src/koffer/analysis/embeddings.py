"""Versioned float32 embedding cache (docs/17, docs/19).

Layout:
    ``$XDG_CACHE_HOME/koffer/embeddings/<model-version>/<sample-id>.f32``
    ``$XDG_CACHE_HOME/koffer/embeddings/<model-version>/<sample-id>.json``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId
from koffer.filesystem.hashing import content_fingerprint

__all__ = [
    "EmbeddingRecord",
    "EmbeddingStore",
]


@dataclass(frozen=True, slots=True)
class EmbeddingRecord:
    """Cached embedding vector + sidecar metadata."""

    sample_id: EntityId
    model_version: str
    source_fingerprint: str
    dimensions: int
    checksum: str
    vector: np.ndarray

    def __post_init__(self) -> None:
        if self.vector.dtype != np.float32 or self.vector.ndim != 1:
            object.__setattr__(
                self,
                "vector",
                np.asarray(self.vector, dtype=np.float32).reshape(-1),
            )


class EmbeddingStore:
    """Filesystem cache for rebuildable embedding vectors."""

    def __init__(self, cache_dir: Path) -> None:
        self._root = Path(cache_dir) / "embeddings"

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, sample_id: EntityId, model_version: str) -> Path:
        return self._root / _safe_version(model_version) / f"{sample_id}.f32"

    def meta_path_for(self, sample_id: EntityId, model_version: str) -> Path:
        return self._root / _safe_version(model_version) / f"{sample_id}.json"

    def get(self, sample_id: EntityId, model_version: str) -> EmbeddingRecord | None:
        vector_path = self.path_for(sample_id, model_version)
        meta_path = self.meta_path_for(sample_id, model_version)
        if not vector_path.is_file() or not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            vector = np.fromfile(vector_path, dtype=np.float32)
        except (OSError, json.JSONDecodeError, ValueError):
            return None
        dims = int(meta.get("dimensions", 0))
        if dims <= 0 or vector.size != dims:
            return None
        checksum = content_fingerprint(vector_path)
        if checksum != str(meta.get("checksum", "")):
            return None
        return EmbeddingRecord(
            sample_id=sample_id,
            model_version=str(meta.get("model_version", model_version)),
            source_fingerprint=str(meta.get("source_fingerprint", "")),
            dimensions=dims,
            checksum=checksum,
            vector=vector.astype(np.float32),
        )

    def put(
        self,
        sample_id: EntityId,
        *,
        model_version: str,
        source_fingerprint: str,
        vector: np.ndarray,
    ) -> EmbeddingRecord:
        arr = np.asarray(vector, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            raise ValidationError("Embedding vector must be non-empty")
        vector_path = self.path_for(sample_id, model_version)
        meta_path = self.meta_path_for(sample_id, model_version)
        vector_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = vector_path.with_suffix(".f32.tmp")
        arr.tofile(tmp)
        tmp.replace(vector_path)
        checksum = content_fingerprint(vector_path)
        meta = {
            "sample_id": str(sample_id),
            "model_version": model_version,
            "source_fingerprint": source_fingerprint,
            "dimensions": int(arr.size),
            "checksum": checksum,
        }
        meta_tmp = meta_path.with_suffix(".json.tmp")
        meta_tmp.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        meta_tmp.replace(meta_path)
        return EmbeddingRecord(
            sample_id=sample_id,
            model_version=model_version,
            source_fingerprint=source_fingerprint,
            dimensions=int(arr.size),
            checksum=checksum,
            vector=arr,
        )

    def list_for_model(self, model_version: str) -> list[EmbeddingRecord]:
        directory = self._root / _safe_version(model_version)
        if not directory.is_dir():
            return []
        records: list[EmbeddingRecord] = []
        for meta_path in sorted(directory.glob("*.json")):
            sample_id = EntityId(meta_path.stem)
            record = self.get(sample_id, model_version)
            if record is not None:
                records.append(record)
        return records

    def invalidate(self, sample_id: EntityId, model_version: str) -> None:
        for path in (
            self.path_for(sample_id, model_version),
            self.meta_path_for(sample_id, model_version),
        ):
            if path.is_file():
                path.unlink()


def _safe_version(model_version: str) -> str:
    cleaned = model_version.strip().replace("/", "_").replace("\\", "_")
    return cleaned or "unknown"
