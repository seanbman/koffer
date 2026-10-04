"""PreparationService recipes and FFmpeg render: source hashes must stay unchanged."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import ConflictAction, JobState
from koffer.domain.preparation import (
    NormalizeSpec,
    PreparationRecipe,
    RenderOptions,
    TrimSpec,
)
from koffer.filesystem.hashing import content_fingerprint
from koffer.jobs import JobScheduler
from koffer.persistence import ConnectionFactory, apply_migrations
from koffer.repositories.job_items import JobItemRepository
from koffer.repositories.samples import SampleRepository
from koffer.services.preparation import PreparationService
from koffer.services.sources import SourceService


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _build(
    tmp_path: Path,
) -> tuple[PreparationService, SourceService, JobScheduler, ConnectionFactory]:
    factory = ConnectionFactory(tmp_path / "library.sqlite3")
    apply_migrations(factory.get_connection())
    scheduler = JobScheduler(factory, io_workers=2, render_workers=1)
    sources = SourceService(factory, scheduler)
    preparation = PreparationService(factory, scheduler)
    return preparation, sources, scheduler, factory


def test_save_recipe_does_not_modify_source_bytes(tmp_path: Path) -> None:
    preparation, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        media = write_sine_wav(pack / "kick.wav", duration_s=0.5)
        before = content_fingerprint(media)
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        recipe = PreparationRecipe(
            trim=TrimSpec(start_ms=50, end_ms=400),
            fade_out_ms=20,
            gain_db=-1.5,
            reverse=True,
        )
        preparation.save_recipe(sample.id, recipe)
        loaded = preparation.get_recipe(sample.id)
        assert loaded.trim.start_ms == 50
        assert loaded.reverse is True
        assert content_fingerprint(media) == before

        preparation.reset_recipe(sample.id)
        assert preparation.get_recipe(sample.id) == PreparationRecipe.default()
        assert content_fingerprint(media) == before
    finally:
        scheduler.shutdown(wait=True)


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg required for render")
def test_render_produces_new_file_and_source_hash_unchanged(tmp_path: Path) -> None:
    preparation, sources, scheduler, factory = _build(tmp_path)
    try:
        pack = tmp_path / "pack"
        pack.mkdir()
        media = write_sine_wav(pack / "loop.wav", duration_s=1.0, channels=2)
        before_hash = content_fingerprint(media)
        source = sources.add_source(pack)
        assert scheduler.wait(sources.scan(source.id), timeout=30.0).state is JobState.COMPLETED
        sample = SampleRepository(factory.get_connection()).list_by_source(source.id)[0]

        recipe = PreparationRecipe(
            trim=TrimSpec(start_ms=100, end_ms=800),
            fade_in_ms=10,
            fade_out_ms=15,
            gain_db=-2.0,
            normalize=NormalizeSpec(enabled=False),
            reverse=True,
            channels="mono",
            output_format="wav",
        )
        preparation.save_recipe(sample.id, recipe)
        out_dir = tmp_path / "renders"
        plan = preparation.plan_render(
            sample.id,
            recipe,
            RenderOptions(
                destination_dir=str(out_dir),
                filename="loop_prepared.wav",
                conflict_policy=ConflictAction.KEEP_BOTH,
                carry_metadata=False,
            ),
        )
        assert Path(plan.destination_path) != media
        assert plan.source_content_hash == before_hash
        assert plan.ffmpeg_argv
        assert plan.ffmpeg_argv[0].endswith("ffmpeg") or "ffmpeg" in plan.ffmpeg_argv[0]
        # shell=False contract: argv is a list of discrete tokens (no joined shell string).
        assert all("&&" not in part for part in plan.ffmpeg_argv)

        job_id = preparation.execute_render(plan)
        job = scheduler.wait(job_id, timeout=60.0)
        assert job.state is JobState.COMPLETED, job.summary_json
        summary = json.loads(job.summary_json or "{}")
        assert summary.get("source_hash_unchanged") is True
        destination = Path(summary["destination_path"])
        assert destination.is_file()
        assert destination.stat().st_size > 0
        assert destination.resolve() != media.resolve()
        assert content_fingerprint(media) == before_hash

        item = JobItemRepository(factory.get_connection()).list_for_job(job_id)[0]
        detail = json.loads(item.detail_json or "{}")
        assert detail.get("source_hash_unchanged") is True
    finally:
        scheduler.shutdown(wait=True)


@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg required for render")
def test_direct_ffmpeg_render_leaves_source_hash(tmp_path: Path) -> None:
    """Lower-level pipeline proof used when service wiring is exercised separately."""
    from koffer.audio.render import run_ffmpeg_render

    source = write_sine_wav(tmp_path / "src.wav", duration_s=0.4)
    before = content_fingerprint(source)
    output = tmp_path / "out.wav"
    run_ffmpeg_render(
        source,
        output,
        PreparationRecipe(trim=TrimSpec(start_ms=20, end_ms=300), reverse=True),
    )
    assert output.is_file()
    assert content_fingerprint(source) == before
    # Sanity: ffmpeg can probe the output.
    probed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    assert probed.returncode == 0
