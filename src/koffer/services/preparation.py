"""PreparationService: non-destructive recipes and FFmpeg render plans (docs/19, docs/27)."""

from __future__ import annotations

from pathlib import Path

from koffer.audio.render import (
    build_render_command,
    ensure_ffmpeg_available,
    resolve_ffmpeg,
)
from koffer.domain.enums import ConflictAction, JobType
from koffer.domain.errors import NotFoundError, PathUnavailableError, ValidationError
from koffer.domain.ids import EntityId, new_entity_id
from koffer.domain.preparation import (
    PreparationRecipe,
    PreviewHandle,
    RenderOptions,
    RenderPlan,
)
from koffer.domain.timestamps import utc_now_iso
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import keep_both_destination, path_fingerprint
from koffer.jobs.scheduler import JobScheduler, JobSpec
from koffer.persistence.connection import ConnectionFactory
from koffer.repositories.preparation_recipes import PreparationRecipeRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.technical_metadata import TechnicalMetadataRepository

__all__ = [
    "PreparationRecipe",
    "PreparationService",
    "PreviewHandle",
    "RenderOptions",
    "RenderPlan",
]


class PreparationService:
    """Non-destructive preparation recipes and argv-safe FFmpeg render orchestration."""

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        scheduler: JobScheduler | None = None,
    ) -> None:
        self._factory = connection_factory
        self._scheduler = scheduler

    def resolve_media_path(self, sample_id: EntityId) -> Path | None:
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None or sample.source_id is None:
            return None
        source = SourceRepository(conn).get(sample.source_id)
        if source is None:
            return None
        return Path(source.root_path) / sample.relative_path

    def get_recipe(self, sample_id: EntityId) -> PreparationRecipe:
        """Return stored recipe or the default identity recipe (never mutates audio)."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        row = PreparationRecipeRepository(conn).get_by_sample(sample_id)
        if row is None:
            return PreparationRecipe.default()
        return row.recipe

    def save_recipe(self, sample_id: EntityId, recipe: PreparationRecipe) -> None:
        """Persist recipe JSON only; source audio bytes are never touched."""
        recipe.validate()
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        PreparationRecipeRepository(conn).upsert(sample_id, recipe)

    def reset_recipe(self, sample_id: EntityId) -> None:
        """Delete stored recipe (restore defaults) without touching source audio."""
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        PreparationRecipeRepository(conn).delete_by_sample(sample_id)

    def create_preview(self, sample_id: EntityId, recipe: PreparationRecipe) -> PreviewHandle:
        """Return a preview handle; foundations mark approximate quality (docs/19)."""
        recipe.validate()
        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        media = self.resolve_media_path(sample_id)
        if media is None or not media.is_file():
            raise PathUnavailableError(f"Sample media unavailable: {sample_id}")
        return PreviewHandle(
            sample_id=sample_id,
            recipe=recipe,
            quality="approximate",
        )

    def plan_render(
        self,
        sample_id: EntityId,
        recipe: PreparationRecipe,
        output: RenderOptions,
    ) -> RenderPlan:
        """Build a reviewed render plan with argv constructed from typed recipe values."""
        recipe.validate()
        if not output.destination_dir.strip():
            raise ValidationError("destination_dir is required")
        if not output.filename.strip():
            raise ValidationError("filename is required")
        if output.conflict_policy is ConflictAction.REVIEW:
            raise ValidationError("render conflict_policy must be keep_both, skip, or replace")
        if output.conflict_policy is ConflictAction.CHOOSE_DESTINATION:
            raise ValidationError("choose_destination is not supported for render foundations")

        conn = self._factory.get_connection()
        sample = SampleRepository(conn).get(sample_id)
        if sample is None:
            raise NotFoundError(f"Sample not found: {sample_id}")
        media = self.resolve_media_path(sample_id)
        if media is None or not media.is_file():
            raise PathUnavailableError(f"Sample media unavailable: {sample_id}")

        # Prefer recipe.output_format extension over caller typo.
        stem = Path(output.filename).stem
        destination = Path(output.destination_dir) / f"{stem}.{recipe.output_format}"
        if destination.resolve() == media.resolve():
            raise ValidationError("render must not overwrite the source path")

        if destination.exists():
            if output.conflict_policy is ConflictAction.KEEP_BOTH:
                destination = keep_both_destination(destination)
            elif output.conflict_policy is ConflictAction.SKIP:
                raise ValidationError(
                    f"destination exists and conflict_policy is skip: {destination}"
                )
            elif output.conflict_policy is ConflictAction.REPLACE:
                pass  # explicit replace allowed at finalize time
            else:
                raise ValidationError(f"unsupported conflict_policy: {output.conflict_policy}")

        source_rate: int | None = None
        tech = TechnicalMetadataRepository(conn).get(sample_id)
        if tech is not None and tech.sample_rate_hz > 0:
            source_rate = tech.sample_rate_hz

        ffmpeg_bin = resolve_ffmpeg()
        argv: tuple[str, ...] = ()
        if ffmpeg_bin is not None:
            command = build_render_command(
                media,
                destination,
                recipe,
                ffmpeg_bin=ffmpeg_bin,
                source_sample_rate_hz=source_rate,
            )
            argv = command.argv

        return RenderPlan(
            id=str(new_entity_id()),
            sample_id=sample_id,
            source_path=str(media),
            source_content_hash=content_fingerprint(media),
            source_fingerprint=path_fingerprint(media),
            destination_path=str(destination),
            recipe=recipe,
            conflict_policy=output.conflict_policy,
            carry_metadata=output.carry_metadata,
            carry_artwork=output.carry_artwork,
            created_at=utc_now_iso(),
            collection_id=output.collection_id,
            ffmpeg_argv=argv,
        )

    def execute_render(self, plan: RenderPlan) -> EntityId:
        """Enqueue a RENDER Job; never mutates the source path."""
        if self._scheduler is None:
            raise ValidationError("JobScheduler is required to execute render")
        ensure_ffmpeg_available()
        media = Path(plan.source_path)
        if not media.is_file():
            raise PathUnavailableError(f"source unavailable: {plan.source_path}")
        if content_fingerprint(media) != plan.source_content_hash:
            raise ValidationError("source content changed since plan was created")
        if path_fingerprint(media) != plan.source_fingerprint:
            raise ValidationError("source fingerprint changed since plan was created")
        dest = Path(plan.destination_path)
        if dest.resolve() == media.resolve():
            raise ValidationError("render must not overwrite the source path")
        return self._scheduler.submit(JobSpec(type=JobType.RENDER, scope=plan.to_scope()))
