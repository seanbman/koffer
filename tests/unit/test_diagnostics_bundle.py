"""Diagnostics bundle excludes audio/waveforms/embeddings by default."""

from __future__ import annotations

import zipfile
from pathlib import Path

from koffer.app_context import AppContext
from koffer.audio.wav_fixtures import write_sine_wav
from koffer.diagnostics import build_diagnostics_bundle


def test_diagnostics_bundle_excludes_audio_by_default(tmp_path: Path) -> None:
    context = AppContext.open_temp(tmp_path / "diag")
    try:
        # Bait audio under data and cache trees.
        bait_data = context.paths.data_dir / "managed-audio" / "secret.wav"
        bait_data.parent.mkdir(parents=True)
        write_sine_wav(bait_data, duration_s=0.05)

        waveform = context.paths.cache_dir / "waveforms" / "1" / "sample.bin"
        waveform.parent.mkdir(parents=True)
        waveform.write_bytes(b"FAKE-WAVEFORM")

        embedding = context.paths.cache_dir / "embeddings" / "model" / "sample.f32"
        embedding.parent.mkdir(parents=True)
        embedding.write_bytes(b"FAKE-EMBEDDING")

        log_path = context.paths.log_dir / "koffer.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("info ok\n", encoding="utf-8")

        destination = tmp_path / "out" / "diagnostics.zip"
        result = build_diagnostics_bundle(
            destination,
            paths=context.paths,
            connection_factory=context.connection_factory,
            include_audio=False,
        )
        assert result.path.is_file()
        assert result.excludes_audio_by_default is True

        with zipfile.ZipFile(result.path, "r") as zf:
            names = set(zf.namelist())
        assert "manifest.json" in names
        assert "INCLUDED.txt" in names
        assert "logs/koffer.log" in names

        joined = "\n".join(names).lower()
        assert "secret.wav" not in joined
        assert ".wav" not in joined
        assert "waveforms/" not in joined
        assert "embeddings/" not in joined
        assert "FAKE-WAVEFORM" not in joined

        # Excluded list should mention the bait paths we refused.
        excluded = "\n".join(result.excluded_names).lower()
        assert "secret.wav" in excluded or "managed-audio" in excluded
        assert "waveforms" in excluded
        assert "embeddings" in excluded
    finally:
        context.close()
