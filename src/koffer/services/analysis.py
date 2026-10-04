"""AnalysisService: deterministic analysis queue + Suggestion review (docs/06, docs/27)."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from koffer.analysis.heuristics import DIM_BPM, DIM_KEY
from koffer.analysis.pipeline import (
    DETERMINISTIC_PIPELINE_VERSION,
    DETERMINISTIC_PROVIDER,
    DETERMINISTIC_PROVIDER_VERSION,
    run_deterministic_analysis,
)
from koffer.domain.enums import (
    AnalysisDepth,
    AnalysisRunState,
    ClassificationDimension,
    ClassificationSource,
    JobType,
    SuggestionStatus,
)
from koffer.domain.errors import NotFoundError, ValidationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.models import Classification, Suggestion
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import path_fingerprint
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.analysis_runs import (
    AnalysisFeature,
    AnalysisFeatureRepository,
    AnalysisRun,
    AnalysisRunRepository,
)
from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.suggestions import SuggestionRepository

if TYPE_CHECKING:
    from koffer.jobs.scheduler import JobScheduler

__all__ = [
    "AnalysisService",
    "AnalysisState",
    "AnalysisStateKind",
    "SuggestionAction",
    "SuggestionActionKind",
    "SuggestionReviewItem",
]


class AnalysisStateKind(StrEnum):
    """Coarse analysis lifecycle for UI badges."""

    NEVER_RUN = "never_run"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALE = "stale"


class SuggestionActionKind(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    EDIT = "edit"


@dataclass(frozen=True, slots=True)
class SuggestionAction:
    """One batch-review action (docs/27 AnalysisService.batch_review)."""

    suggestion_id: EntityId
    action: SuggestionActionKind
    edited_value: str | None = None


@dataclass(frozen=True, slots=True)
class AnalysisState:
    sample_id: EntityId
    kind: AnalysisStateKind
    pipeline_version: str | None
    source_fingerprint: str | None
    pending_suggestion_count: int
    last_run_id: EntityId | None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class SuggestionReviewItem:
    """S10 inbox row with Sample path context."""

    suggestion: Suggestion
    sample_filename: str
    sample_relative_path: str
    sample_id: EntityId


_CLASSIFICATION_DIMENSIONS = {d.value for d in ClassificationDimension}
_MUSICAL_DIMENSIONS = {DIM_BPM, DIM_KEY}


class AnalysisService:
    """Queue deterministic analysis and review Suggestions without embedded writes."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        scheduler: JobScheduler | None = None,
    ) -> None:
        self._factory = connection_factory
        self._scheduler = scheduler

    def queue_for_sample(
        self,
        sample_id: EntityId,
        depth: AnalysisDepth = AnalysisDepth.DETERMINISTIC,
    ) -> EntityId:
        """Enqueue deterministic analysis for one Sample. Returns Job id."""
        from koffer.jobs.scheduler import JobSpec

        if depth not in {AnalysisDepth.DETERMINISTIC, AnalysisDepth.FULL}:
            raise ValidationError(f"Unsupported analysis depth: {depth}")
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to queue analysis")
        # FULL currently queues deterministic analysis; semantic Suggestions fuse later.
        return self._scheduler.submit(
            JobSpec(
                type=JobType.DETERMINISTIC_ANALYSIS,
                scope={"sample_ids": [str(sample_id)], "depth": str(depth)},
            )
        )

    def queue_for_source(
        self,
        source_id: EntityId,
        depth: AnalysisDepth = AnalysisDepth.DETERMINISTIC,
    ) -> EntityId:
        from koffer.jobs.scheduler import JobSpec

        if depth not in {AnalysisDepth.DETERMINISTIC, AnalysisDepth.FULL}:
            raise ValidationError(f"Unsupported analysis depth: {depth}")
        conn = self._factory.get_connection()
        source = SourceRepository(conn).get(source_id)
        if source is None:
            raise NotFoundError(f"Source not found: {source_id}")
        samples = SampleRepository(conn).list_by_source(source_id)
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to queue analysis")
        return self._scheduler.submit(
            JobSpec(
                type=JobType.DETERMINISTIC_ANALYSIS,
                scope={
                    "sample_ids": [str(s.id) for s in samples],
                    "source_id": str(source_id),
                    "depth": str(depth),
                },
            )
        )

    def analyze_sample(self, sample_id: EntityId) -> EntityId:
        """Run deterministic analysis synchronously for one Sample. Returns analysis_run id.

        Never writes embedded metadata. Never overwrites confirmed classifications.
        """
        conn = self._factory.get_connection()
        samples = SampleRepository(conn)
        sources = SourceRepository(conn)
        classifications = ClassificationRepository(conn)
        suggestions = SuggestionRepository(conn)
        runs = AnalysisRunRepository(conn)
        features = AnalysisFeatureRepository(conn)

        sample = samples.get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")

        media_path: Path | None = None
        fingerprint = f"missing:{sample.id}"
        if sample.source_id is not None:
            source = sources.get(sample.source_id)
            if source is not None:
                candidate = Path(source.root_path) / sample.relative_path
                if candidate.is_file():
                    media_path = candidate
                    fingerprint = f"{path_fingerprint(candidate)}:{content_fingerprint(candidate)}"

        now = utc_now_iso()
        run_id = new_entity_id()
        run = AnalysisRun(
            id=run_id,
            sample_id=sample_id,
            pipeline_version=DETERMINISTIC_PIPELINE_VERSION,
            source_fingerprint=fingerprint,
            state=AnalysisRunState.RUNNING,
            started_at=now,
        )
        runs.create(run)

        try:
            result = run_deterministic_analysis(
                relative_path=sample.relative_path,
                filename=sample.filename,
                media_path=media_path,
            )
        except Exception as exc:  # noqa: BLE001 — persist failure, do not raise through Job
            failed = replace(
                run,
                state=AnalysisRunState.FAILED,
                completed_at=utc_now_iso(),
                error_code=type(exc).__name__,
            )
            runs.update(failed)
            raise

        for draft in result.features:
            features.create(
                AnalysisFeature(
                    id=new_entity_id(),
                    analysis_run_id=run_id,
                    name=draft.name,
                    value_json=draft.value_json,
                    provider_version=draft.provider_version,
                )
            )

        confirmed = classifications.list_for_sample(sample_id)
        confirmed_pairs = {(c.dimension.value, c.value) for c in confirmed}

        # Supersede prior pending proposals for dimensions we are about to refresh.
        proposal_dims = {p.dimension for p in result.proposals}
        suggestions.supersede_pending_for_sample(
            sample_id,
            reviewed_at=now,
            dimensions=proposal_dims,
        )

        for proposal in result.proposals:
            # Never overwrite confirmed classifications: skip an already-confirmed
            # dimension+value pair. Other values on the same dimension may still be
            # proposed (docs/05 allows coexisting labels like Kick + Drum).
            if proposal.dimension in _CLASSIFICATION_DIMENSIONS:
                if (proposal.dimension, proposal.proposed_value) in confirmed_pairs:
                    continue
            elif proposal.dimension in _MUSICAL_DIMENSIONS:
                # Musical dims are not classifications; still skip if an accepted
                # Suggestion already confirmed the same value.
                existing_accepted = [
                    s
                    for s in suggestions.list_for_sample(
                        sample_id, status=SuggestionStatus.ACCEPTED
                    )
                    if s.dimension == proposal.dimension
                    and s.proposed_value == proposal.proposed_value
                ]
                if existing_accepted:
                    continue
            else:
                continue

            suggestions.create(
                Suggestion(
                    id=new_entity_id(),
                    sample_id=sample_id,
                    dimension=proposal.dimension,
                    proposed_value=proposal.proposed_value,
                    confidence=proposal.confidence,
                    status=SuggestionStatus.PENDING,
                    evidence_json=proposal.evidence_json,
                    provider=DETERMINISTIC_PROVIDER,
                    provider_version=DETERMINISTIC_PROVIDER_VERSION,
                    analysis_run_id=run_id,
                    created_at=now,
                )
            )

        completed = replace(
            run,
            state=AnalysisRunState.COMPLETED,
            completed_at=utc_now_iso(),
            error_code=result.bpm_key_error if not result.bpm_key_ok else None,
        )
        runs.update(completed)
        return run_id

    def accept_suggestion(
        self,
        suggestion_id: EntityId,
        edited_value: str | None = None,
    ) -> None:
        """Accept (optionally edit) a Suggestion into confirmed library metadata.

        Does not write embedded audio tags.
        """
        conn = self._factory.get_connection()
        suggestions = SuggestionRepository(conn)
        classifications = ClassificationRepository(conn)
        suggestion = suggestions.get(suggestion_id)
        if suggestion is None:
            raise NotFoundError(f"Suggestion not found: {suggestion_id}")
        if suggestion.status is not SuggestionStatus.PENDING:
            raise ValidationError(
                f"Suggestion is not pending: {suggestion.status}",
                detail=str(suggestion_id),
            )

        value = edited_value if edited_value is not None else suggestion.proposed_value
        value = value.strip()
        if not value:
            raise ValidationError("Accepted value must be non-empty")

        now = utc_now_iso()
        updated = replace(
            suggestion,
            proposed_value=value,
            status=SuggestionStatus.ACCEPTED,
            reviewed_at=now,
        )
        suggestions.update(updated)

        if suggestion.dimension in _CLASSIFICATION_DIMENSIONS:
            dimension = ClassificationDimension(suggestion.dimension)
            existing = [
                c
                for c in classifications.list_for_sample(suggestion.sample_id)
                if c.dimension is dimension and c.value == value
            ]
            if not existing:
                classifications.create(
                    Classification(
                        id=new_entity_id(),
                        sample_id=suggestion.sample_id,
                        dimension=dimension,
                        value=value,
                        source=ClassificationSource.ACCEPTED_SUGGESTION,
                        created_at=now,
                        updated_at=now,
                    )
                )
        # Musical bpm/key accepts retain Suggestion provenance only; features remain
        # on analysis_runs and are never written into the audio file.

    def reject_suggestion(self, suggestion_id: EntityId) -> None:
        """Reject a Suggestion while retaining the row for provenance/history."""
        conn = self._factory.get_connection()
        suggestions = SuggestionRepository(conn)
        suggestion = suggestions.get(suggestion_id)
        if suggestion is None:
            raise NotFoundError(f"Suggestion not found: {suggestion_id}")
        if suggestion.status is not SuggestionStatus.PENDING:
            raise ValidationError(
                f"Suggestion is not pending: {suggestion.status}",
                detail=str(suggestion_id),
            )
        suggestions.update(
            replace(
                suggestion,
                status=SuggestionStatus.REJECTED,
                reviewed_at=utc_now_iso(),
            )
        )

    def batch_review(self, actions: list[SuggestionAction]) -> None:
        """Apply accept/reject/edit actions. Scope is exactly ``actions``."""
        for action in actions:
            if action.action is SuggestionActionKind.REJECT:
                self.reject_suggestion(action.suggestion_id)
            elif action.action in {SuggestionActionKind.ACCEPT, SuggestionActionKind.EDIT}:
                self.accept_suggestion(action.suggestion_id, edited_value=action.edited_value)
            else:
                raise ValidationError(f"Unknown suggestion action: {action.action}")

    def get_analysis_state(self, sample_id: EntityId) -> AnalysisState:
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        run = AnalysisRunRepository(conn).latest_for_sample(sample_id)
        pending = len(
            SuggestionRepository(conn).list_for_sample(sample_id, status=SuggestionStatus.PENDING)
        )
        if run is None:
            return AnalysisState(
                sample_id=sample_id,
                kind=AnalysisStateKind.NEVER_RUN,
                pipeline_version=None,
                source_fingerprint=None,
                pending_suggestion_count=pending,
                last_run_id=None,
            )

        kind = AnalysisStateKind.COMPLETED
        if run.state is AnalysisRunState.QUEUED:
            kind = AnalysisStateKind.QUEUED
        elif run.state is AnalysisRunState.RUNNING:
            kind = AnalysisStateKind.RUNNING
        elif run.state is AnalysisRunState.FAILED:
            kind = AnalysisStateKind.FAILED
        elif run.state is AnalysisRunState.COMPLETED and sample.source_id is not None:
            source = SourceRepository(conn).get(sample.source_id)
            if source is not None:
                media = Path(source.root_path) / sample.relative_path
                if media.is_file():
                    current = f"{path_fingerprint(media)}:{content_fingerprint(media)}"
                    if current != run.source_fingerprint:
                        kind = AnalysisStateKind.STALE

        return AnalysisState(
            sample_id=sample_id,
            kind=kind,
            pipeline_version=run.pipeline_version,
            source_fingerprint=run.source_fingerprint,
            pending_suggestion_count=pending,
            last_run_id=run.id,
            error_code=run.error_code,
        )

    def list_pending_suggestions(
        self,
        *,
        limit: int = 500,
        offset: int = 0,
        min_confidence: float | None = None,
        dimension: str | None = None,
    ) -> list[SuggestionReviewItem]:
        """S10 inbox: pending Suggestions with Sample path context."""
        conn = self._factory.get_connection()
        suggestions = SuggestionRepository(conn).list_by_status(
            SuggestionStatus.PENDING, limit=limit, offset=offset
        )
        samples = SampleRepository(conn)
        items: list[SuggestionReviewItem] = []
        for suggestion in suggestions:
            if min_confidence is not None and suggestion.confidence < min_confidence:
                continue
            if dimension is not None and suggestion.dimension != dimension:
                continue
            sample = samples.get(suggestion.sample_id)
            if sample is None:
                continue
            items.append(
                SuggestionReviewItem(
                    suggestion=suggestion,
                    sample_filename=sample.filename,
                    sample_relative_path=sample.relative_path,
                    sample_id=sample.id,
                )
            )
        return items

    def pending_count(self) -> int:
        return SuggestionRepository(self._factory.get_connection()).count_by_status(
            SuggestionStatus.PENDING
        )

    def evidence_summary(self, suggestion_id: EntityId) -> str:
        """Human-readable evidence summary for S10 inspector."""
        suggestion = SuggestionRepository(self._factory.get_connection()).get(suggestion_id)
        if suggestion is None:
            raise NotFoundError(f"Suggestion not found: {suggestion_id}")
        try:
            payload = json.loads(suggestion.evidence_json)
        except json.JSONDecodeError:
            return suggestion.evidence_json
        return json.dumps(payload, indent=2, sort_keys=True)
