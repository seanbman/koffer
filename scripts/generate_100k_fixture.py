#!/usr/bin/env python3
"""Generate the docs/20 synthetic 100k Sample DB/manifest fixture (no audio corpus)."""

from __future__ import annotations

import argparse
from pathlib import Path

from koffer.dev.synthetic_library import DEFAULT_SAMPLE_COUNT, DEFAULT_SEED, build_synthetic_library


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/performance/fixtures/100k"),
        help="Directory for library.sqlite3 + manifest.json",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=DEFAULT_SAMPLE_COUNT,
        help="Number of synthetic Sample rows (default: 100000)",
    )
    parser.add_argument(
        "--seed",
        default=DEFAULT_SEED,
        help="Deterministic seed label for entity IDs",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even when a matching fixture already exists",
    )
    args = parser.parse_args(argv)
    result = build_synthetic_library(
        args.output_dir,
        sample_count=args.sample_count,
        seed=args.seed,
        force=args.force,
    )
    print(f"database: {result.paths.database_path}")
    print(f"manifest: {result.paths.manifest_path}")
    print(f"sample_count: {result.sample_count}")
    print(f"audio_files_created: {result.audio_files_created}")
    print(f"database_sha256: {result.database_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
