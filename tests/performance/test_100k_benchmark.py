"""docs/20: synthetic 100k fixture + performance benchmark report."""

from __future__ import annotations

import json
import os
from pathlib import Path

from koffer.dev.perf_benchmark import percentile_nearest_rank, run_100k_benchmark
from koffer.dev.synthetic_library import build_synthetic_library

_WORK = Path(__file__).resolve().parents[2]
_DEFAULT_FIXTURE = _WORK / "tests" / "performance" / "fixtures" / "100k"
_DEFAULT_REPORT = _WORK / "tests" / "performance" / "reports" / "100k_benchmark_report.json"
_PROMOTE_REPORT = (
    Path("/home/sean/Documents/experiments/csw-041026/.dreadnought/scratch/koffer/promote")
    / "order-rg-1-100k-benchmark-report.json"
)


def test_percentile_nearest_rank() -> None:
    assert percentile_nearest_rank([10.0], 95.0) == 10.0
    assert percentile_nearest_rank([1.0, 2.0, 3.0, 4.0], 50.0) == 2.0


def test_small_synthetic_fixture_has_no_audio_files(tmp_path: Path) -> None:
    result = build_synthetic_library(tmp_path / "tiny", sample_count=50, force=True)
    assert result.sample_count == 50
    assert result.audio_files_created == 0
    assert result.manifest["audio_files_materialized"] is False
    assert result.paths.database_path.is_file()
    assert result.paths.manifest_path.is_file()
    # No wav/flac/aiff/mp3 files under the fixture root.
    audio = [
        path
        for path in result.paths.root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".wav", ".flac", ".aiff", ".mp3", ".ogg"}
    ]
    assert audio == []


def test_100k_fixture_and_benchmark_report() -> None:
    """Build 100k DB/manifest (no audio corpus), measure timings, write report."""
    # Prefer durable fixture dir under tests/ so local reruns reuse the corpus.
    fixture_dir = Path(os.environ.get("KOFFER_PERF_FIXTURE_DIR", str(_DEFAULT_FIXTURE)))
    report_path = Path(os.environ.get("KOFFER_PERF_REPORT_PATH", str(_DEFAULT_REPORT)))

    report = run_100k_benchmark(
        fixture_dir=fixture_dir,
        report_path=report_path,
        sample_count=100_000,
        force_rebuild=False,
    )

    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sample_count"] == 100_000
    assert manifest["audio_files_materialized"] is False
    assert manifest["audio_files_created"] == 0

    audio = [
        path
        for path in fixture_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".wav", ".flac", ".aiff", ".mp3", ".ogg"}
        and "app-runtime" not in path.parts
    ]
    assert audio == []

    assert report_path.is_file()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    names = {item["name"] for item in payload["timings"]}
    assert names == {"app_shell_ms", "common_query_p95_ms", "first_200_rows_ms"}
    assert "summary" in payload
    assert payload["sample_count"] == 100_000
    # Pass absolute targets OR explicitly document hardware-limited variance.
    assert payload["overall_pass"] or payload["hardware_limited_variance"]
    assert report.sample_count == 100_000

    # Mirror report into promote/ for Order evidence (best-effort outside work tree).
    try:
        _PROMOTE_REPORT.parent.mkdir(parents=True, exist_ok=True)
        _PROMOTE_REPORT.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        pass
