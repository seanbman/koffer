#!/usr/bin/env python3
"""Verify direct production dependency licenses and emit THIRD_PARTY_NOTICES.txt."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "packaging" / "license_inventory.json"
PYPROJECT_PATH = ROOT / "pyproject.toml"
DEFAULT_NOTICES = ROOT / "THIRD_PARTY_NOTICES.txt"


def _load_inventory() -> dict[str, object]:
    if not INVENTORY_PATH.is_file():
        raise SystemExit(f"missing license inventory: {INVENTORY_PATH}")
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _direct_deps_from_pyproject() -> list[str]:
    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    # Narrow parse of [project] dependencies = [ ... ] without toml dependency.
    match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text)
    if not match:
        raise SystemExit("could not locate project.dependencies in pyproject.toml")
    names: list[str] = []
    for raw in re.findall(r'"([^"]+)"', match.group(1)):
        name = re.split(r"[<>=!~\[]", raw, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    if not names:
        raise SystemExit("no direct dependencies parsed from pyproject.toml")
    return sorted(names)


def _normalize_dep_name(name: str) -> str:
    return name.replace("_", "-").casefold()


def verify(inventory: dict[str, object]) -> list[str]:
    allowed = {str(x) for x in inventory.get("allowed_spdx", [])}  # type: ignore[arg-type]
    recorded = inventory.get("direct_dependencies", {})
    exceptions = inventory.get("exceptions", {})
    if not isinstance(recorded, dict) or not isinstance(exceptions, dict):
        raise SystemExit("license inventory schema invalid")

    recorded_norm = {_normalize_dep_name(str(k)): (str(k), v) for k, v in recorded.items()}
    errors: list[str] = []
    for dep in _direct_deps_from_pyproject():
        key = _normalize_dep_name(dep)
        if key not in recorded_norm:
            errors.append(f"unrecorded direct dependency: {dep}")
            continue
        _canon, meta = recorded_norm[key]
        if not isinstance(meta, dict):
            errors.append(f"invalid inventory entry for {dep}")
            continue
        spdx = str(meta.get("spdx", ""))
        if spdx in allowed:
            continue
        exc = exceptions.get(_canon) or exceptions.get(dep)
        if isinstance(exc, dict) and str(exc.get("spdx", "")) == spdx:
            continue
        errors.append(
            f"disallowed or unexcepted license for {dep}: {spdx!r} (allowed={sorted(allowed)})"
        )

    # Fail if inventory lists packages not in pyproject (drift).
    py_norm = {_normalize_dep_name(d) for d in _direct_deps_from_pyproject()}
    for key, (canon, _) in recorded_norm.items():
        if key not in py_norm:
            errors.append(f"inventory lists dependency absent from pyproject: {canon}")
    return errors


def render_notices(inventory: dict[str, object]) -> str:
    recorded = inventory.get("direct_dependencies", {})
    assert isinstance(recorded, dict)
    lines = [
        "Koffer third-party notices",
        "==========================",
        "",
        "Koffer application source is MIT licensed (see LICENSE).",
        "This file lists direct production dependencies packaged with release builds.",
        "Model weight redistribution is handled separately via manifest policy; weights",
        "are not bundled in the V1 AppImage by default.",
        "",
    ]
    for name in sorted(recorded, key=str.casefold):
        meta = recorded[name]
        assert isinstance(meta, dict)
        lines.append(f"{name}")
        lines.append(f"  SPDX: {meta.get('spdx', 'UNKNOWN')}")
        lines.append(f"  Role: {meta.get('role', '')}")
        notes = str(meta.get("notes", "") or "").strip()
        if notes:
            lines.append(f"  Notes: {notes}")
        lines.append("")
    exceptions = inventory.get("exceptions", {})
    if isinstance(exceptions, dict) and exceptions:
        lines.append("Explicit exceptions")
        lines.append("-------------------")
        for name, meta in sorted(exceptions.items(), key=lambda kv: str(kv[0]).casefold()):
            if not isinstance(meta, dict):
                continue
            lines.append(f"{name}: {meta.get('spdx')} — {meta.get('rationale', '')}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-notices",
        type=Path,
        nargs="?",
        const=DEFAULT_NOTICES,
        default=None,
        help=f"Write notices file (default path: {DEFAULT_NOTICES})",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify inventory only; do not write notices.",
    )
    args = parser.parse_args(argv)

    inventory = _load_inventory()
    errors = verify(inventory)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    notices = render_notices(inventory)
    if args.check_only:
        print("license verification OK")
        return 0
    if args.write_notices is not None:
        args.write_notices.parent.mkdir(parents=True, exist_ok=True)
        args.write_notices.write_text(notices, encoding="utf-8")
        print(f"wrote {args.write_notices}")
    else:
        print(notices)
    print("license verification OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
