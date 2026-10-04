"""Offscreen pytest-qt coverage for S11 Similar Sounds foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QWidget

from koffer.analysis.semantic import FakeSemanticProvider
from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import JobState
from koffer.repositories.samples import SampleRepository
from koffer.services.similarity import SimilarityService
from koffer.ui.shell import MainWindow


def test_s11_model_absent_explains_and_library_still_opens(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s11-absent")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick.wav", duration_s=0.15)
    try:
        source = context.source_service.add_source(pack)
        assert (
            context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0).state
            is JobState.COMPLETED
        )
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S01")
        assert window.current_screen_id() == "S01"

        window.open_similar_sounds(samples[0].id, filename=samples[0].filename)
        assert window.current_screen_id() == "S11"
        screen = window.findChild(QWidget, "similarSoundsScreen")
        assert screen is not None
        status = window.findChild(QLabel, "similarSoundsStatus")
        assert status is not None
        assert "unavailable" in status.text().lower()
        seed = window.findChild(QLabel, "similarSoundsSeed")
        assert seed is not None
        assert "kick.wav" in seed.text()
    finally:
        context.close()


def test_s11_with_fake_provider_lists_similarity_scores(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s11-fake")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick_a.wav", duration_s=0.12)
    write_sine_wav(pack / "kick_b.wav", duration_s=0.12)
    try:
        source = context.source_service.add_source(pack)
        assert (
            context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0).state
            is JobState.COMPLETED
        )
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        service = SimilarityService(
            context.connection_factory,
            context.paths.cache_dir,
            provider=FakeSemanticProvider(embedding_dim=32),
            media_resolver=context.resolve_sample_media_path,
        )
        for sample in samples:
            service.ensure_embedding(sample.id)
        context.similarity_service = service

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        seed = next(item for item in samples if "kick_a" in item.filename)
        window.open_similar_sounds(seed.id, filename=seed.filename)
        listing = window.findChild(QListWidget, "similarSoundsList")
        assert listing is not None
        assert listing.count() >= 2
        # Seed pinned + at least one scored neighbor.
        assert "SEED" in listing.item(0).text()
        neighbor_texts = [listing.item(i).text() for i in range(1, listing.count())]
        assert any(text[:1].isdigit() for text in neighbor_texts)
        preview = window.findChild(QPushButton, "similarSoundsPreviewButton")
        assert preview is not None
    finally:
        context.close()
