"""Similarity index build/query over fixture embeddings."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from koffer.analysis.similarity_index import SimilarityIndex
from koffer.domain.ids import new_entity_id


def test_similarity_index_ranks_nearest_neighbor(tmp_path: Path) -> None:
    dim = 16
    seed = new_entity_id()
    near = new_entity_id()
    far = new_entity_id()
    base = np.zeros(dim, dtype=np.float32)
    base[0] = 1.0
    near_vec = base.copy()
    near_vec[1] = 0.05
    far_vec = np.zeros(dim, dtype=np.float32)
    far_vec[-1] = 1.0

    index = SimilarityIndex(tmp_path, model_version="fixture-v1", embedding_dim=dim)
    index.build([(seed, base), (near, near_vec), (far, far_vec)])
    hits = index.query(base, limit=2, exclude=seed)
    assert len(hits) == 2
    assert hits[0].sample_id == near
    assert hits[0].score > hits[1].score

    # Persist + reload
    reloaded = SimilarityIndex(tmp_path, model_version="fixture-v1", embedding_dim=dim)
    assert reloaded.load() is True
    again = reloaded.query(base, limit=1, exclude=seed)
    assert again[0].sample_id == near
