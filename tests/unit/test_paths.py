"""Unit smoke for XDG path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from koffer.config.paths import resolve_app_paths


def test_resolve_app_paths_uses_koffer_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    paths = resolve_app_paths()
    assert paths.config_dir.name == "koffer"
    assert paths.data_dir.name == "koffer"
    assert paths.cache_dir.name == "koffer"
    assert paths.log_dir.name == "logs"
    paths.ensure()
    assert paths.log_dir.is_dir()
