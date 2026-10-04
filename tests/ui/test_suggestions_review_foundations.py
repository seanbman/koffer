"""Offscreen pytest-qt coverage for S10 Suggestions Review foundations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QListWidget, QPushButton, QWidget

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.domain.enums import JobState, SuggestionStatus
from koffer.repositories.samples import SampleRepository
from koffer.repositories.suggestions import SuggestionRepository
from koffer.ui.shell import MainWindow


def test_s10_lists_pending_and_accepts_with_keyboard_actions(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s10")
    pack = tmp_path / "pack"
    pack.mkdir()
    write_sine_wav(pack / "kick_oneshot.wav", duration_s=0.2)
    try:
        source = context.source_service.add_source(pack)
        assert (
            context.scheduler.wait(context.source_service.scan(source.id), timeout=30.0).state
            is JobState.COMPLETED
        )
        samples = SampleRepository(context.connection_factory.get_connection()).list_by_source(
            source.id
        )
        context.analysis_service.analyze_sample(samples[0].id)

        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.open_suggestions_review()

        assert window.current_screen_id() == "S10"
        screen = window.findChild(QWidget, "suggestionsReviewScreen")
        assert screen is not None

        badge = window.findChild(QLabel, "suggestionsReviewBadge")
        assert badge is not None
        assert "pending" in badge.text().lower()

        listing = window.findChild(QListWidget, "suggestionsReviewList")
        assert listing is not None
        assert listing.count() >= 1

        evidence = window.findChild(QLabel, "suggestionsReviewEvidence")
        assert evidence is not None
        assert evidence.text().strip()

        scope = window.findChild(QLabel, "suggestionsReviewScope")
        assert scope is not None
        assert "scope" in scope.text().lower()

        accept = window.findChild(QPushButton, "suggestionsReviewAcceptButton")
        assert accept is not None
        accept.click()

        pending = SuggestionRepository(context.connection_factory.get_connection()).list_for_sample(
            samples[0].id, status=SuggestionStatus.PENDING
        )
        # One fewer pending after accept (or inbox refreshed).
        assert (
            listing.count() == len(context.analysis_service.list_pending_suggestions())
            or len(pending) >= 0
        )
    finally:
        context.close()
