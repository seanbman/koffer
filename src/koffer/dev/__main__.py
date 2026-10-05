"""``python -m koffer.dev <command>`` entrypoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from koffer.analysis.manifest import check_model_manifest
from koffer.config.paths import resolve_app_paths
from koffer.dev.synthetic_library import DEFAULT_SAMPLE_COUNT, DEFAULT_SEED, build_synthetic_library


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="koffer.dev", description="Koffer developer tools")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser(
        "model-manifest-check",
        help="Validate packaged model manifest and optional cached artifact checksum",
    )
    manifest.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional override manifest path",
    )
    manifest.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional cache dir containing models/ (defaults to XDG cache)",
    )
    manifest.add_argument(
        "--require-artifact",
        action="store_true",
        help="Fail when the weight artifact is absent",
    )

    smoke = sub.add_parser(
        "model-smoke",
        help="Report whether the default semantic provider is available (no download)",
    )
    smoke.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Optional cache dir containing models/",
    )

    fixture = sub.add_parser(
        "generate-100k-fixture",
        help="Build synthetic 100k Sample DB/manifest without audio files (docs/20)",
    )
    fixture.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/performance/fixtures/100k"),
        help="Directory for library.sqlite3 + manifest.json",
    )
    fixture.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    fixture.add_argument("--seed", default=DEFAULT_SEED)
    fixture.add_argument("--force", action="store_true")

    bench = sub.add_parser(
        "benchmark-100k",
        help="Run docs/20 timing benchmark against the synthetic 100k fixture",
    )
    bench.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/performance/fixtures/100k"),
    )
    bench.add_argument(
        "--report-path",
        type=Path,
        default=Path("tests/performance/reports/100k_benchmark_report.json"),
    )
    bench.add_argument("--force-rebuild", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "model-manifest-check":
        cache_dir = args.cache_dir if args.cache_dir is not None else resolve_app_paths().cache_dir
        result = check_model_manifest(
            manifest_path=args.manifest,
            cache_dir=cache_dir,
            require_artifact=args.require_artifact,
        )
        for message in result.messages:
            print(message)
        return 0 if result.ok else 1

    if args.command == "model-smoke":
        from koffer.analysis.panns import PannsSemanticProvider

        cache_dir = args.cache_dir if args.cache_dir is not None else resolve_app_paths().cache_dir
        provider = PannsSemanticProvider(cache_dir)
        if provider.is_available():
            print(f"available: {provider.provider_id}@{provider.model_version}")
            return 0
        print(f"unavailable: {provider.unavailable_reason()}")
        return 0  # absence is not a failure for smoke foundations

    if args.command == "generate-100k-fixture":
        fixture_result = build_synthetic_library(
            args.output_dir,
            sample_count=args.sample_count,
            seed=args.seed,
            force=args.force,
        )
        print(f"database: {fixture_result.paths.database_path}")
        print(f"manifest: {fixture_result.paths.manifest_path}")
        print(f"sample_count: {fixture_result.sample_count}")
        print(f"audio_files_created: {fixture_result.audio_files_created}")
        return 0

    if args.command == "benchmark-100k":
        from koffer.dev.perf_benchmark import run_100k_benchmark

        bench_report = run_100k_benchmark(
            fixture_dir=args.fixture_dir,
            report_path=args.report_path,
            force_rebuild=args.force_rebuild,
        )
        print(bench_report.summary)
        for timing in bench_report.timings:
            status = "PASS" if timing.passed else "FAIL"
            print(
                f"{timing.name}: {timing.measured_ms:.3f}ms "
                f"(target {timing.target_ms:.0f}ms) [{status}]"
            )
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
