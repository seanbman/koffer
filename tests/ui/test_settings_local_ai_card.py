"""S18 Local AI card: plain-language states and real/disabled actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from koffer.analysis.manifest import load_model_manifest
from koffer.app_context import AppContext
from koffer.services.local_ai import LocalAiStatusKind
from koffer.ui.shell import MainWindow


def test_settings_local_ai_card_shows_readable_states(qtbot: object, tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "s18-local-ai")
    try:
        window = MainWindow(context, directory_picker=lambda _p: None)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        window.navigate("S18")

        card = window.findChild(QWidget, "settingsLocalAiCard")
        assert card is not None
        # Foundation checkbox must be gone.
        assert window.findChild(QWidget, "settingsLocalModelEnabled") is None

        state = window.findChild(QLabel, "settingsLocalAiState")
        headline = window.findChild(QLabel, "settingsLocalAiHeadline")
        privacy = window.findChild(QLabel, "settingsLocalAiPrivacy")
        install = window.findChild(QPushButton, "settingsLocalAiInstallButton")
        enable = window.findChild(QPushButton, "settingsLocalAiEnableButton")
        backfill = window.findChild(QPushButton, "settingsLocalAiBackfillButton")
        assert state is not None and headline is not None and privacy is not None
        assert install is not None and enable is not None and backfill is not None

        status = context.local_ai_service.status()
        assert "computer" in privacy.text().lower()
        assert status.kind.value.replace("_", " ").upper() in state.text()

        if status.kind is LocalAiStatusKind.MANIFEST_BLOCKED:
            assert not install.isEnabled()
            assert "checksum" in (install.toolTip().lower() + status.detail.lower())
            assert not enable.isEnabled()
            assert not backfill.isEnabled()
        elif status.kind is LocalAiStatusKind.NOT_INSTALLED:
            packaged = load_model_manifest()
            if packaged.checksum_recorded:
                assert install.isEnabled()
            assert not enable.isEnabled()
            assert not backfill.isEnabled()
            assert "not installed" in headline.text().lower()
        else:
            # ERROR / other recoverable: actions are either real or explained.
            assert install.isEnabled() or enable.isEnabled() or (not backfill.isEnabled())
    finally:
        context.close()
