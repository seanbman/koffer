"""Typed preparation_recipes repository (non-destructive; never mutates audio)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.preparation import PreparationRecipe
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories._sqlite import as_entity_id


@dataclass(frozen=True, slots=True)
class PreparationRecipeRow:
    """Persisted preparation recipe row."""

    id: EntityId
    sample_id: EntityId
    recipe_version: int
    recipe: PreparationRecipe
    updated_at: str


class PreparationRecipeRepository:
    """One active recipe per Sample for V1 (docs/17)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_by_sample(self, sample_id: EntityId) -> PreparationRecipeRow | None:
        row = self._conn.execute(
            """
            SELECT id, sample_id, recipe_version, recipe_json, updated_at
            FROM preparation_recipes
            WHERE sample_id = ?
            """,
            (str(sample_id),),
        ).fetchone()
        if row is None:
            return None
        recipe = PreparationRecipe.from_json(json.loads(str(row["recipe_json"])))
        return PreparationRecipeRow(
            id=as_entity_id(row["id"]),
            sample_id=as_entity_id(row["sample_id"]),
            recipe_version=int(row["recipe_version"]),
            recipe=recipe,
            updated_at=str(row["updated_at"]),
        )

    def upsert(self, sample_id: EntityId, recipe: PreparationRecipe) -> PreparationRecipeRow:
        recipe.validate()
        existing = self.get_by_sample(sample_id)
        now = utc_now_iso()
        payload = json.dumps(recipe.to_json(), sort_keys=True)
        if existing is None:
            row_id = new_entity_id()
            self._conn.execute(
                """
                INSERT INTO preparation_recipes (
                    id, sample_id, recipe_version, recipe_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(row_id), str(sample_id), recipe.version, payload, now),
            )
        else:
            row_id = existing.id
            self._conn.execute(
                """
                UPDATE preparation_recipes
                SET recipe_version = ?, recipe_json = ?, updated_at = ?
                WHERE sample_id = ?
                """,
                (recipe.version, payload, now, str(sample_id)),
            )
        stored = self.get_by_sample(sample_id)
        assert stored is not None
        assert stored.id == row_id
        return stored

    def delete_by_sample(self, sample_id: EntityId) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM preparation_recipes WHERE sample_id = ?",
            (str(sample_id),),
        )
        return int(cursor.rowcount) > 0
