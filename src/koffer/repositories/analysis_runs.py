"""Typed analysis_runs / analysis_features repositories."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from koffer.domain.enums import AnalysisRunState
from koffer.domain.ids import EntityId
from koffer.repositories._sqlite import as_entity_id, optional_str, row_count


@dataclass(frozen=True, slots=True)
class AnalysisRun:
    id: EntityId
    sample_id: EntityId
    pipeline_version: str
    source_fingerprint: str
    state: AnalysisRunState
    started_at: str
    completed_at: str | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisFeature:
    id: EntityId
    analysis_run_id: EntityId
    name: str
    value_json: str
    provider_version: str


def _run_from_row(row: sqlite3.Row) -> AnalysisRun:
    return AnalysisRun(
        id=as_entity_id(row["id"]),
        sample_id=as_entity_id(row["sample_id"]),
        pipeline_version=str(row["pipeline_version"]),
        source_fingerprint=str(row["source_fingerprint"]),
        state=AnalysisRunState(str(row["state"])),
        started_at=str(row["started_at"]),
        completed_at=optional_str(row["completed_at"]),
        error_code=optional_str(row["error_code"]),
    )


def _feature_from_row(row: sqlite3.Row) -> AnalysisFeature:
    return AnalysisFeature(
        id=as_entity_id(row["id"]),
        analysis_run_id=as_entity_id(row["analysis_run_id"]),
        name=str(row["name"]),
        value_json=str(row["value_json"]),
        provider_version=str(row["provider_version"]),
    )


class AnalysisRunRepository:
    """CRUD for analysis_runs rows."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, run: AnalysisRun) -> None:
        self._conn.execute(
            """
            INSERT INTO analysis_runs (
                id, sample_id, pipeline_version, source_fingerprint, state,
                started_at, completed_at, error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(run.id),
                str(run.sample_id),
                run.pipeline_version,
                run.source_fingerprint,
                str(run.state),
                run.started_at,
                run.completed_at,
                run.error_code,
            ),
        )

    def get(self, run_id: EntityId) -> AnalysisRun | None:
        row = self._conn.execute(
            "SELECT * FROM analysis_runs WHERE id = ?",
            (str(run_id),),
        ).fetchone()
        return None if row is None else _run_from_row(row)

    def latest_for_sample(self, sample_id: EntityId) -> AnalysisRun | None:
        row = self._conn.execute(
            """
            SELECT * FROM analysis_runs
            WHERE sample_id = ?
            ORDER BY completed_at DESC NULLS LAST, started_at DESC, id DESC
            LIMIT 1
            """,
            (str(sample_id),),
        ).fetchone()
        return None if row is None else _run_from_row(row)

    def update(self, run: AnalysisRun) -> bool:
        return (
            row_count(
                self._conn,
                """
                UPDATE analysis_runs SET
                    sample_id = ?,
                    pipeline_version = ?,
                    source_fingerprint = ?,
                    state = ?,
                    started_at = ?,
                    completed_at = ?,
                    error_code = ?
                WHERE id = ?
                """,
                (
                    str(run.sample_id),
                    run.pipeline_version,
                    run.source_fingerprint,
                    str(run.state),
                    run.started_at,
                    run.completed_at,
                    run.error_code,
                    str(run.id),
                ),
            )
            > 0
        )


class AnalysisFeatureRepository:
    """CRUD for analysis_features rows."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(self, feature: AnalysisFeature) -> None:
        self._conn.execute(
            """
            INSERT INTO analysis_features (
                id, analysis_run_id, name, value_json, provider_version
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(feature.id),
                str(feature.analysis_run_id),
                feature.name,
                feature.value_json,
                feature.provider_version,
            ),
        )

    def list_for_run(self, analysis_run_id: EntityId) -> list[AnalysisFeature]:
        rows = self._conn.execute(
            """
            SELECT * FROM analysis_features
            WHERE analysis_run_id = ?
            ORDER BY name ASC, id ASC
            """,
            (str(analysis_run_id),),
        ).fetchall()
        return [_feature_from_row(row) for row in rows]
