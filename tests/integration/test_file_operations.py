"""Safety regressions for FileOperationService Copy/Move/Reference."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from koffer.app_context import AppContext
from koffer.domain.enums import ConflictAction, FileOperationKind, JobItemState, JobState
from koffer.domain.errors import ValidationError
from koffer.filesystem.hashing import content_fingerprint
from koffer.filesystem.operations import verified_copy, verified_move
from koffer.repositories.samples import SampleRepository
from koffer.services.file_operations import ConflictPolicy


def _write_audio(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _index_one(context: AppContext, pack: Path) -> object:
    source = context.source_service.add_source(pack)
    job_id = context.source_service.scan(source.id)
    finished = context.scheduler.wait(job_id, timeout=30.0)
    assert finished.state is JobState.COMPLETED
    samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
        source.id
    )
    assert len(samples) == 1
    return samples[0]


def test_verified_copy_preserves_hash_and_uses_temp_pattern(tmp_path: Path) -> None:
    src = _write_audio(tmp_path / "src" / "kick.wav", b"RIFF-COPY-BYTES-001")
    dst = tmp_path / "dst" / "kick.wav"
    before = content_fingerprint(src)
    got = verified_copy(src, dst)
    assert got == before
    assert content_fingerprint(dst) == before
    assert content_fingerprint(src) == before
    assert src.read_bytes() == b"RIFF-COPY-BYTES-001"
    # No leftover temp siblings.
    temps = list((tmp_path / "dst").glob(".kick.wav.koffer-tmp-*"))
    assert temps == []


def test_verified_copy_refuses_silent_overwrite(tmp_path: Path) -> None:
    src = _write_audio(tmp_path / "a.wav", b"NEW-BYTES")
    dst = _write_audio(tmp_path / "b.wav", b"EXISTING")
    with pytest.raises(FileExistsError):
        verified_copy(src, dst, overwrite=False)
    assert dst.read_bytes() == b"EXISTING"


def test_copy_plan_default_conflict_is_review_not_replace(
    tmp_path: Path,
) -> None:
    context = AppContext.open_temp(tmp_path / "ctx-review")
    try:
        pack = tmp_path / "pack"
        sample_path = _write_audio(pack / "kick.wav", b"RIFF-KICK")
        sample = _index_one(context, pack)
        dest = tmp_path / "managed"
        dest.mkdir()
        existing = dest / "kick.wav"
        existing.write_bytes(b"ALREADY-HERE")
        before_existing = existing.read_bytes()
        before_source = sample_path.read_bytes()

        plan = context.file_operation_service.plan_copy([sample.id], dest)
        assert plan.kind is FileOperationKind.COPY
        assert plan.conflict_policy.default_action is ConflictAction.REVIEW
        assert len(plan.items) == 1
        assert plan.items[0].conflict is True
        assert plan.items[0].conflict_action is ConflictAction.REVIEW
        assert plan.unresolved_conflicts()

        with pytest.raises(ValidationError, match="unresolved conflicts"):
            context.file_operation_service.execute(plan)

        assert existing.read_bytes() == before_existing
        assert sample_path.read_bytes() == before_source
    finally:
        context.close()


def test_copy_preserves_original_hash_via_service(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "ctx-copy")
    try:
        pack = tmp_path / "pack"
        sample_path = _write_audio(pack / "snare.wav", b"RIFF-SNARE-HASH")
        sample = _index_one(context, pack)
        source_hash = content_fingerprint(sample_path)
        dest = tmp_path / "managed"
        dest.mkdir()

        plan = context.file_operation_service.plan_copy([sample.id], dest)
        job_id = context.file_operation_service.execute(plan)
        finished = context.scheduler.wait(job_id, timeout=30.0)
        assert finished.state is JobState.COMPLETED

        dest_file = dest / "snare.wav"
        assert dest_file.is_file()
        assert content_fingerprint(dest_file) == source_hash
        assert content_fingerprint(sample_path) == source_hash
        assert sample_path.is_file()

        items = context.file_operation_service.list_item_results(job_id)
        assert len(items) == 1
        assert items[0].state is JobItemState.SUCCEEDED
        summary = json.loads(finished.summary_json or "{}")
        assert summary["succeeded"] == 1
        assert summary["failed"] == 0
        assert summary["skipped"] == 0
    finally:
        context.close()


def test_partial_failure_reports_per_item_states(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "ctx-partial")
    try:
        pack = tmp_path / "pack"
        a = _write_audio(pack / "a.wav", b"AAA")
        b = _write_audio(pack / "b.wav", b"BBB")
        source = context.source_service.add_source(pack)
        job_id = context.source_service.scan(source.id)
        assert context.scheduler.wait(job_id, timeout=30.0).state is JobState.COMPLETED
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        assert len(samples) == 2
        by_name = {s.filename: s for s in samples}

        dest = tmp_path / "managed"
        dest.mkdir()
        # Pre-create conflict for b; resolve a as normal, b as skip.
        (dest / "b.wav").write_bytes(b"EXISTING-B")
        plan = context.file_operation_service.plan_copy(
            [by_name["a.wav"].id, by_name["b.wav"].id],
            dest,
        )
        assert any(item.conflict for item in plan.items)
        resolved = context.file_operation_service.resolve_conflicts(
            plan,
            {
                by_name["b.wav"].id: ConflictAction.SKIP,
            },
        )
        # a has no conflict; b skipped.
        job_id = context.file_operation_service.execute(resolved)
        finished = context.scheduler.wait(job_id, timeout=30.0)
        assert finished.state is JobState.COMPLETED
        summary = json.loads(finished.summary_json or "{}")
        assert summary["succeeded"] == 1
        assert summary["skipped"] == 1
        assert summary["failed"] == 0

        items = {
            Path(item.source_path or "").name: item
            for item in context.file_operation_service.list_item_results(job_id)
        }
        assert items["a.wav"].state is JobItemState.SUCCEEDED
        assert items["b.wav"].state is JobItemState.SKIPPED
        assert (dest / "a.wav").is_file()
        assert (dest / "b.wav").read_bytes() == b"EXISTING-B"
        assert a.is_file() and b.is_file()
    finally:
        context.close()


def test_move_same_filesystem_and_reference_no_mutation(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "ctx-move-ref")
    try:
        pack = tmp_path / "pack"
        sample_path = _write_audio(pack / "hat.wav", b"RIFF-HAT")
        sample = _index_one(context, pack)
        source_hash = content_fingerprint(sample_path)

        ref_plan = context.file_operation_service.plan_reference([sample.id])
        assert ref_plan.kind is FileOperationKind.REFERENCE
        assert all(item.destination_path is None for item in ref_plan.items)
        ref_job = context.file_operation_service.execute(ref_plan)
        ref_finished = context.scheduler.wait(ref_job, timeout=30.0)
        assert ref_finished.state is JobState.COMPLETED
        assert sample_path.is_file()
        assert content_fingerprint(sample_path) == source_hash

        dest = tmp_path / "managed"
        dest.mkdir()
        move_plan = context.file_operation_service.plan_move([sample.id], dest)
        move_job = context.file_operation_service.execute(move_plan)
        move_finished = context.scheduler.wait(move_job, timeout=30.0)
        assert move_finished.state is JobState.COMPLETED
        dest_file = dest / "hat.wav"
        assert dest_file.is_file()
        assert content_fingerprint(dest_file) == source_hash
        assert not sample_path.exists()
    finally:
        context.close()


def test_cross_filesystem_move_deletes_only_after_verified_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = _write_audio(tmp_path / "src" / "tom.wav", b"RIFF-TOM-CROSS")
    dst = tmp_path / "dst" / "tom.wav"
    source_hash = content_fingerprint(src)

    monkeypatch.setattr(
        "koffer.filesystem.operations.same_filesystem",
        lambda _source, _dest_parent: False,
    )
    got = verified_move(src, dst, overwrite=False)
    assert got == source_hash
    assert dst.is_file()
    assert content_fingerprint(dst) == source_hash
    assert not src.exists()


def test_keep_both_avoids_overwrite(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "ctx-keep-both")
    try:
        pack = tmp_path / "pack"
        _write_audio(pack / "kick.wav", b"RIFF-NEW")
        sample = _index_one(context, pack)
        dest = tmp_path / "managed"
        dest.mkdir()
        (dest / "kick.wav").write_bytes(b"RIFF-OLD")

        plan = context.file_operation_service.plan_copy(
            [sample.id],
            dest,
            conflict_policy=ConflictPolicy(default_action=ConflictAction.KEEP_BOTH),
        )
        assert not plan.unresolved_conflicts()
        assert plan.items[0].destination_path is not None
        assert plan.items[0].destination_path.endswith("kick (2).wav")
        job_id = context.file_operation_service.execute(plan)
        finished = context.scheduler.wait(job_id, timeout=30.0)
        assert finished.state is JobState.COMPLETED
        assert (dest / "kick.wav").read_bytes() == b"RIFF-OLD"
        assert (dest / "kick (2).wav").read_bytes() == b"RIFF-NEW"
    finally:
        context.close()
