"""MaintenanceService backup/restore roundtrip preserves user-authored state."""

from __future__ import annotations

import json
from pathlib import Path

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import (
    ClassificationDimension,
    ClassificationSource,
    JobState,
    SampleAvailability,
    SourceStatus,
)
from koffer.domain.ids import new_entity_id
from koffer.domain.models import Classification, Sample, Source
from koffer.domain.preparation import PreparationRecipe, TrimSpec
from koffer.domain.timestamps import utc_now_iso
from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.preparation_recipes import PreparationRecipeRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.sources import SourceRepository
from koffer.services.collections import CollectionService


def test_maintenance_backup_restore_preserves_collections_classifications_recipes(
    tmp_path: Path,
) -> None:
    context = AppContext.open_temp(tmp_path / "maint")
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        write_sine_wav(pack / "kick.wav", duration_s=0.1)

        now = utc_now_iso()
        source = Source(
            id=new_entity_id(),
            display_name="Pack",
            root_path=str(pack.resolve()),
            enabled=True,
            recursive=True,
            status=SourceStatus.ONLINE,
            created_at=now,
            updated_at=now,
        )
        conn = context.connection_factory.get_connection()
        SourceRepository(conn).create(source)
        sample = Sample(
            id=new_entity_id(),
            source_id=source.id,
            relative_path="kick.wav",
            normalized_path_cache="kick.wav",
            filename="kick.wav",
            extension="wav",
            size_bytes=100,
            mtime_ns=1,
            availability=SampleAvailability.ONLINE,
            favorite=False,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        SampleRepository(conn).create(sample)
        classification = Classification(
            id=new_entity_id(),
            sample_id=sample.id,
            dimension=ClassificationDimension.SAMPLE_TYPE,
            value="one-shot",
            source=ClassificationSource.USER,
            created_at=now,
            updated_at=now,
        )
        ClassificationRepository(conn).create(classification)
        recipe = PreparationRecipe(trim=TrimSpec(start_ms=10, end_ms=80))
        PreparationRecipeRepository(conn).upsert(sample.id, recipe)

        collections = CollectionService(context.connection_factory)
        collection = collections.create("Favorites", description="user pack")
        collections.add_samples(collection.id, [sample.id])

        backup_parent = tmp_path / "backups"
        backup_parent.mkdir()
        backup_job_id = context.maintenance_service.backup(backup_parent)
        backup_job = context.scheduler.wait(backup_job_id, timeout=60.0)
        assert backup_job.state is JobState.COMPLETED
        summary = json.loads(backup_job.summary_json or "{}")
        assert summary.get("ok") is True
        assert "koffer-backup-" in str(summary.get("backup_dir", ""))

        backup_dirs = sorted(backup_parent.glob("koffer-backup-*"))
        assert len(backup_dirs) == 1
        backup_dir = backup_dirs[0]

        # Mutate live DB so restore must bring back original user state.
        collections.delete(collection.id)
        ClassificationRepository(conn).delete(classification.id)
        PreparationRecipeRepository(conn).delete_by_sample(sample.id)

        # Close caller connection so restore can replace the DB file safely.
        context.connection_factory.close_thread_connection()
        restore_job_id = context.maintenance_service.restore(backup_dir)
        restore_job = context.scheduler.wait(restore_job_id, timeout=60.0)
        assert restore_job.state is JobState.COMPLETED

        # Reopen on this thread against the restored database.
        context.connection_factory.close_thread_connection()
        restored = context.connection_factory.get_connection()

        restored_collection = CollectionService(context.connection_factory).get(collection.id)
        assert restored_collection.name == "Favorites"
        members = CollectionService(context.connection_factory).list_sample_ids(collection.id)
        assert sample.id in members

        restored_classification = ClassificationRepository(restored).get(classification.id)
        assert restored_classification is not None
        assert restored_classification.value == "one-shot"

        restored_recipe = PreparationRecipeRepository(restored).get_by_sample(sample.id)
        assert restored_recipe is not None
        assert restored_recipe.recipe.trim.start_ms == 10
        assert restored_recipe.recipe.trim.end_ms == 80
    finally:
        context.close()
