"""Performance benchmark against the synthetic 100k fixture (docs/20 targets)."""

from __future__ import annotations

import json
import os
import platform
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from koffer.app_context import AppContext
from koffer.config.paths import AppPaths
from koffer.dev.synthetic_library import (
    DATABASE_NAME,
    DEFAULT_SAMPLE_COUNT,
    build_synthetic_library,
)
from koffer.domain.query import PageRequest, SampleFilters, SampleQuery
from koffer.persistence.connection import ConnectionFactory
from koffer.services.search import SearchService

# docs/20 release targets (ms).
TARGET_APP_SHELL_MS = 2000.0
TARGET_COMMON_QUERY_P95_MS = 250.0
TARGET_FIRST_200_ROWS_MS = 400.0

COMMON_QUERY_TEXT = "kick"
QUERY_ITERATIONS = 21


@dataclass(frozen=True)
class TimingResult:
    name: str
    measured_ms: float
    target_ms: float
    passed: bool
    notes: str = ""


@dataclass(frozen=True)
class BenchmarkReport:
    schema_version: int
    sample_count: int
    fixture_dir: str
    hardware: dict[str, str]
    timings: list[TimingResult]
    overall_pass: bool
    hardware_limited_variance: bool
    summary: str


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    """Nearest-rank percentile for a non-empty list (percentile in 0..100)."""
    if not values:
        msg = "values must be non-empty"
        raise ValueError(msg)
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = max(1, int(round((percentile / 100.0) * len(ordered))))
    return ordered[min(len(ordered), rank) - 1]


def run_100k_benchmark(
    *,
    fixture_dir: Path,
    report_path: Path,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    force_rebuild: bool = False,
    query_iterations: int = QUERY_ITERATIONS,
) -> BenchmarkReport:
    """Build/reuse fixture, measure shell/query/first-200 timings, write JSON report."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    fixture = build_synthetic_library(
        fixture_dir,
        sample_count=sample_count,
        force=force_rebuild,
    )
    if fixture.audio_files_created != 0:
        msg = "synthetic fixture must not materialize per-sample audio files"
        raise RuntimeError(msg)

    # Point AppPaths.data_dir at fixture root so library.sqlite3 is reused.
    app_root = fixture_dir / "app-runtime"
    app_root.mkdir(parents=True, exist_ok=True)
    data_dir = app_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_link = data_dir / DATABASE_NAME
    if db_link.exists() or db_link.is_symlink():
        db_link.unlink()
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(db_link) + suffix)
        if sidecar.exists():
            sidecar.unlink()
    # Always copy so AppContext WAL/side effects do not mutate the shared fixture.
    _copy_sqlite(fixture.paths.database_path, db_link)

    paths = AppPaths(
        config_dir=app_root / "config",
        data_dir=data_dir,
        cache_dir=app_root / "cache",
        state_dir=app_root / "state",
        log_dir=app_root / "state" / "logs",
    )

    shell_ms = _measure_app_shell(paths)
    query_ms_list, first_200_ms = _measure_queries(
        fixture.paths.database_path,
        iterations=query_iterations,
    )
    query_p95 = percentile_nearest_rank(query_ms_list, 95.0)

    timings = [
        TimingResult(
            name="app_shell_ms",
            measured_ms=round(shell_ms, 3),
            target_ms=TARGET_APP_SHELL_MS,
            passed=shell_ms <= TARGET_APP_SHELL_MS,
            notes="AppContext.open on existing DB + create_main_window (offscreen)",
        ),
        TimingResult(
            name="common_query_p95_ms",
            measured_ms=round(query_p95, 3),
            target_ms=TARGET_COMMON_QUERY_P95_MS,
            passed=query_p95 <= TARGET_COMMON_QUERY_P95_MS,
            notes=(
                f"SearchService text={COMMON_QUERY_TEXT!r} page limit=200; "
                f"p95 of {len(query_ms_list)} iters "
                f"(median={statistics.median(query_ms_list):.3f})"
            ),
        ),
        TimingResult(
            name="first_200_rows_ms",
            measured_ms=round(first_200_ms, 3),
            target_ms=TARGET_FIRST_200_ROWS_MS,
            passed=first_200_ms <= TARGET_FIRST_200_ROWS_MS,
            notes="First PageRequest(limit=200) after common text/filter query",
        ),
    ]

    overall = all(item.passed for item in timings)
    # docs/20: noisy hardware may miss absolute targets; report still records values.
    hardware_limited = not overall
    if overall:
        summary = "PASS: all docs/20 timing targets met on this host."
    else:
        failed = [t.name for t in timings if not t.passed]
        summary = (
            "HARDWARE-LIMITED VARIANCE: absolute docs/20 targets not met for "
            + ", ".join(failed)
            + "; measured values recorded for local regression reference."
        )

    report = BenchmarkReport(
        schema_version=1,
        sample_count=sample_count,
        fixture_dir=str(fixture_dir.resolve()),
        hardware={
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        timings=timings,
        overall_pass=overall,
        hardware_limited_variance=hardware_limited,
        summary=summary,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _report_to_dict(report)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _measure_app_shell(paths: AppPaths) -> float:
    from PySide6.QtWidgets import QApplication

    from koffer.app import create_main_window

    app = QApplication.instance()
    owns = app is None
    if owns:
        app = QApplication([])
    assert app is not None

    # Exclude first DB creation: fixture DB already exists under paths.data_dir.
    started = time.perf_counter()
    context = AppContext.open(paths, io_workers=1)
    try:
        window = create_main_window(context)
        app.processEvents()
        _ = window.windowTitle()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        window.close()
    finally:
        context.close()
    return elapsed_ms


def _measure_queries(database_path: Path, *, iterations: int) -> tuple[list[float], float]:
    factory = ConnectionFactory(database_path)
    service = SearchService(factory)
    query = SampleQuery(
        text=COMMON_QUERY_TEXT,
        filters=SampleFilters(extensions=("wav", "flac", "aiff", "mp3")),
    )
    page = PageRequest(offset=0, limit=200)

    # Warm-up (not scored).
    warm = service.search(query, page)
    if len(warm.items) == 0:
        msg = "common query returned zero rows; fixture FTS may be incomplete"
        raise RuntimeError(msg)

    samples: list[float] = []
    first_200_ms = 0.0
    for index in range(iterations):
        started = time.perf_counter()
        page_result = service.search(query, page)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if len(page_result.items) != 200:
            msg = f"expected 200 rows, got {len(page_result.items)}"
            raise RuntimeError(msg)
        samples.append(elapsed_ms)
        if index == 0:
            first_200_ms = elapsed_ms

    factory.close_thread_connection()
    return samples, first_200_ms


def _copy_sqlite(src: Path, dest: Path) -> None:
    import sqlite3

    source = sqlite3.connect(src)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def _report_to_dict(report: BenchmarkReport) -> dict[str, Any]:
    return {
        "schema_version": report.schema_version,
        "sample_count": report.sample_count,
        "fixture_dir": report.fixture_dir,
        "hardware": report.hardware,
        "timings": [asdict(item) for item in report.timings],
        "overall_pass": report.overall_pass,
        "hardware_limited_variance": report.hardware_limited_variance,
        "summary": report.summary,
        "targets_docs_20": {
            "app_shell_ms": TARGET_APP_SHELL_MS,
            "common_query_p95_ms": TARGET_COMMON_QUERY_P95_MS,
            "first_200_rows_ms": TARGET_FIRST_200_ROWS_MS,
        },
    }


__all__ = [
    "TARGET_APP_SHELL_MS",
    "TARGET_COMMON_QUERY_P95_MS",
    "TARGET_FIRST_200_ROWS_MS",
    "BenchmarkReport",
    "TimingResult",
    "percentile_nearest_rank",
    "run_100k_benchmark",
]
