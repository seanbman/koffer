"""``python -m koffer.dev <command>`` entrypoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from koffer.analysis.manifest import check_model_manifest
from koffer.config.paths import resolve_app_paths


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

    return 2


if __name__ == "__main__":
    sys.exit(main())
