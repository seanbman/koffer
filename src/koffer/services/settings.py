"""Lightweight settings store for S17–S19 foundations (docs/08, docs/28)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from typing import Any

from koffer.domain.timestamps import utc_now_iso
from koffer.persistence.connection import ConnectionFactory

__all__ = [
    "GeneralSettings",
    "LibraryAnalysisSettings",
    "AudioInterfaceSettings",
    "SettingsService",
]

_SETTINGS_KEY = "app.settings.v1"


@dataclass
class GeneralSettings:
    restore_last_workspace: bool = True
    show_notifications: bool = True
    confirm_non_destructive: bool = True
    # Destructive filesystem confirmations cannot be globally disabled (docs/15).
    confirm_destructive_filesystem: bool = True
    managed_library_path: str = ""
    database_path: str = ""
    temp_render_path: str = ""
    update_policy: str = "manual"


@dataclass
class LibraryAnalysisSettings:
    recursive_scanning: bool = True
    skip_hidden_folders: bool = True
    automatic_analysis: bool = True
    analysis_concurrency: int = 2
    idle_only_deep_analysis: bool = True
    waveform_cache_enabled: bool = True
    similarity_indexing: bool = True
    local_model_enabled: bool = True
    cache_limit_mb: int = 4096


@dataclass
class AudioInterfaceSettings:
    output_device: str = "default"
    preview_gain: float = 0.8
    auto_preview: bool = False
    loop_preview_default: bool = False
    ui_density: str = "comfortable"
    inspector_default_open: bool = True
    theme: str = "dark"
    reduced_motion: bool = False


@dataclass
class AppSettings:
    general: GeneralSettings
    library_analysis: LibraryAnalysisSettings
    audio_interface: AudioInterfaceSettings


class SettingsService:
    """Persist settings JSON in the settings table; live-applicable where safe."""

    def __init__(self, connection_factory: ConnectionFactory) -> None:
        self._factory = connection_factory

    def load(self) -> AppSettings:
        conn = self._factory.get_connection()
        row = conn.execute(
            "SELECT value_json FROM settings WHERE key = ?",
            (_SETTINGS_KEY,),
        ).fetchone()
        if row is None:
            return _defaults()
        try:
            payload = json.loads(str(row["value_json"]))
        except json.JSONDecodeError:
            return _defaults()
        if not isinstance(payload, dict):
            return _defaults()
        return _from_payload(payload)

    def save(self, settings: AppSettings) -> AppSettings:
        # Hard invariant: destructive filesystem confirmations stay enabled.
        settings.general.confirm_destructive_filesystem = True
        conn = self._factory.get_connection()
        payload = {
            "general": asdict(settings.general),
            "library_analysis": asdict(settings.library_analysis),
            "audio_interface": asdict(settings.audio_interface),
        }
        conn.execute(
            """
            INSERT INTO settings (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (_SETTINGS_KEY, json.dumps(payload, sort_keys=True), utc_now_iso()),
        )
        return settings

    def update_general(self, **kwargs: Any) -> GeneralSettings:
        settings = self.load()
        for key, value in kwargs.items():
            if hasattr(settings.general, key):
                setattr(settings.general, key, value)
        self.save(settings)
        return settings.general

    def update_library_analysis(self, **kwargs: Any) -> LibraryAnalysisSettings:
        settings = self.load()
        for key, value in kwargs.items():
            if hasattr(settings.library_analysis, key):
                setattr(settings.library_analysis, key, value)
        self.save(settings)
        return settings.library_analysis

    def update_audio_interface(self, **kwargs: Any) -> AudioInterfaceSettings:
        settings = self.load()
        for key, value in kwargs.items():
            if hasattr(settings.audio_interface, key):
                setattr(settings.audio_interface, key, value)
        self.save(settings)
        return settings.audio_interface


def _defaults() -> AppSettings:
    return AppSettings(
        general=GeneralSettings(),
        library_analysis=LibraryAnalysisSettings(),
        audio_interface=AudioInterfaceSettings(),
    )


def _from_payload(payload: dict[str, Any]) -> AppSettings:
    general = _merge_dataclass(GeneralSettings(), payload.get("general"))
    library = _merge_dataclass(LibraryAnalysisSettings(), payload.get("library_analysis"))
    audio = _merge_dataclass(AudioInterfaceSettings(), payload.get("audio_interface"))
    # Enforce non-disableable destructive confirmations.
    general.confirm_destructive_filesystem = True
    return AppSettings(general=general, library_analysis=library, audio_interface=audio)


def _merge_dataclass[T](default: T, payload: object) -> T:
    if not isinstance(payload, dict):
        return default
    values: dict[str, Any] = {}
    for item in fields(default):  # type: ignore[arg-type]
        if item.name in payload:
            values[item.name] = payload[item.name]
        else:
            values[item.name] = getattr(default, item.name)
    cls = type(default)
    return cls(**values)
