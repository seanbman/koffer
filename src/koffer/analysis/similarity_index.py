"""Cosine similarity index: hnswlib when available, numpy fallback for CI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from koffer.domain.errors import ValidationError
from koffer.domain.ids import EntityId

__all__ = [
    "SimilarityHit",
    "SimilarityIndex",
    "hnswlib_available",
]


@dataclass(frozen=True, slots=True)
class SimilarityHit:
    sample_id: EntityId
    score: float


def hnswlib_available() -> bool:
    try:
        import hnswlib  # noqa: F401
    except ImportError:
        return False
    return True


class SimilarityIndex:
    """Per-model-version cosine ANN index persisted under cache."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        model_version: str,
        embedding_dim: int,
    ) -> None:
        if embedding_dim < 1:
            raise ValidationError("embedding_dim must be >= 1")
        self._model_version = model_version
        self._dim = embedding_dim
        self._dir = Path(cache_dir) / "similarity" / _safe_version(model_version)
        self._ids: list[EntityId] = []
        self._matrix: np.ndarray | None = None
        self._hnsw: object | None = None
        self._use_hnsw = hnswlib_available()

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def embedding_dim(self) -> int:
        return self._dim

    @property
    def size(self) -> int:
        return len(self._ids)

    @property
    def backend(self) -> str:
        return "hnswlib" if self._hnsw is not None else "numpy"

    def clear(self) -> None:
        self._ids = []
        self._matrix = None
        self._hnsw = None

    def build(self, items: list[tuple[EntityId, np.ndarray]]) -> None:
        """Replace the index with the provided embedding rows."""
        self.clear()
        if not items:
            self._persist_meta()
            return
        ids: list[EntityId] = []
        rows: list[np.ndarray] = []
        for sample_id, vector in items:
            arr = _l2_normalize(np.asarray(vector, dtype=np.float32).reshape(-1))
            if arr.size != self._dim:
                raise ValidationError(
                    "Embedding dimension mismatch",
                    detail=f"expected={self._dim} actual={arr.size}",
                )
            ids.append(sample_id)
            rows.append(arr)
        matrix = np.stack(rows, axis=0)
        self._ids = ids
        self._matrix = matrix
        if self._use_hnsw:
            self._hnsw = self._build_hnsw(matrix)
        self._persist()

    def query(
        self,
        vector: np.ndarray,
        *,
        limit: int,
        exclude: EntityId | None = None,
    ) -> list[SimilarityHit]:
        if limit < 1:
            return []
        if not self._ids or self._matrix is None:
            return []
        query = _l2_normalize(np.asarray(vector, dtype=np.float32).reshape(-1))
        if query.size != self._dim:
            raise ValidationError(
                "Query embedding dimension mismatch",
                detail=f"expected={self._dim} actual={query.size}",
            )
        # Over-fetch so we can drop the seed and still fill ``limit``.
        fetch = min(len(self._ids), limit + (1 if exclude is not None else 0))
        if self._hnsw is not None:
            labels, distances = self._hnsw.knn_query(query.reshape(1, -1), k=fetch)  # type: ignore[attr-defined]
            hits: list[SimilarityHit] = []
            for label, distance in zip(labels[0], distances[0], strict=True):
                sample_id = self._ids[int(label)]
                if exclude is not None and sample_id == exclude:
                    continue
                # hnswlib cosine space distance ~= 1 - cosine_similarity
                score = float(1.0 - distance)
                hits.append(SimilarityHit(sample_id=sample_id, score=score))
                if len(hits) >= limit:
                    break
            return hits

        scores = self._matrix @ query
        order = np.argsort(-scores)
        hits = []
        for index in order:
            sample_id = self._ids[int(index)]
            if exclude is not None and sample_id == exclude:
                continue
            hits.append(SimilarityHit(sample_id=sample_id, score=float(scores[int(index)])))
            if len(hits) >= limit:
                break
        return hits

    def load(self) -> bool:
        """Load a previously persisted index. Returns False when absent/invalid."""
        meta_path = self._dir / "index.json"
        matrix_path = self._dir / "vectors.f32"
        if not meta_path.is_file() or not matrix_path.is_file():
            return False
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            ids = [EntityId(str(item)) for item in meta.get("sample_ids", [])]
            dim = int(meta.get("embedding_dim", 0))
            if dim != self._dim or not ids:
                return False
            flat = np.fromfile(matrix_path, dtype=np.float32)
            if flat.size != len(ids) * dim:
                return False
            matrix: np.ndarray = flat.reshape(len(ids), dim)
        except (OSError, json.JSONDecodeError, ValueError):
            return False
        self._ids = ids
        self._matrix = matrix
        self._hnsw = self._build_hnsw(matrix) if self._use_hnsw else None
        return True

    def _persist(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        if self._matrix is None:
            self._persist_meta()
            return
        matrix_path = self._dir / "vectors.f32"
        tmp = matrix_path.with_suffix(".f32.tmp")
        self._matrix.astype(np.float32).tofile(tmp)
        tmp.replace(matrix_path)
        self._persist_meta()
        if self._hnsw is not None:
            hnsw_path = self._dir / "index.bin"
            self._hnsw.save_index(str(hnsw_path))  # type: ignore[attr-defined]

    def _persist_meta(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "model_version": self._model_version,
            "embedding_dim": self._dim,
            "sample_ids": [str(item) for item in self._ids],
            "backend": self.backend,
            "size": len(self._ids),
        }
        meta_path = self._dir / "index.json"
        tmp = meta_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(meta_path)

    def _build_hnsw(self, matrix: np.ndarray) -> object:
        import hnswlib

        index = hnswlib.Index(space="cosine", dim=self._dim)
        index.init_index(max_elements=max(1, matrix.shape[0]), ef_construction=200, M=16)
        index.add_items(matrix, np.arange(matrix.shape[0]))
        index.set_ef(max(16, min(200, matrix.shape[0])))
        return index


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        return (arr / norm).astype(np.float32)
    return arr


def _safe_version(model_version: str) -> str:
    cleaned = model_version.strip().replace("/", "_").replace("\\", "_")
    return cleaned or "unknown"
