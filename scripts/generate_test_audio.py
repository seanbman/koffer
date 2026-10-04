#!/usr/bin/env python3
"""Generate small deterministic audio fixtures for tests (docs/20)."""

from __future__ import annotations

import argparse
from pathlib import Path

from koffer.audio.wav_fixtures import generate_default_set


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("fixtures/generated"),
        help="Directory for generated fixture files",
    )
    args = parser.parse_args(argv)
    written = generate_default_set(args.output_dir)
    for name, path in written.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
