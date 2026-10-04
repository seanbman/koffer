"""Packaging desktop/icon/license source checks (Order 14-1)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_file_name_and_no_terminal_true() -> None:
    desktop = ROOT / "packaging" / "koffer.desktop"
    text = desktop.read_text(encoding="utf-8")
    assert "Name=Koffer" in text
    assert "Terminal=true" not in text
    assert "Terminal=false" in text


def test_appimage_scripts_are_executable() -> None:
    for rel in ("scripts/build_appimage.sh", "scripts/smoke_appimage.sh"):
        path = ROOT / rel
        assert path.is_file(), rel
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{rel} must be executable"


def test_icon_placeholder_exists() -> None:
    assert (ROOT / "packaging" / "icons" / "koffer.svg").is_file()


def test_apprun_is_executable_and_defensive() -> None:
    apprun = ROOT / "packaging" / "AppRun"
    assert apprun.is_file()
    assert apprun.stat().st_mode & stat.S_IXUSR
    text = apprun.read_text(encoding="utf-8")
    assert "usr/bin/koffer" in text
    assert "packaged runtime missing" in text


def test_license_inventory_covers_direct_deps() -> None:
    path = ROOT / "packaging" / "license_inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    recorded = {k.casefold() for k in inventory["direct_dependencies"]}
    assert "pyside6" in recorded
    assert "mutagen" in recorded
    assert "numpy" in recorded


def test_verify_licenses_check_only_succeeds() -> None:
    script = ROOT / "scripts" / "verify_licenses.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--check-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_smoke_appimage_dry_run_succeeds() -> None:
    script = ROOT / "scripts" / "smoke_appimage.sh"
    proc = subprocess.run(
        ["bash", str(script), "--dry-run"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_makefile_has_package_target() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\npackage:" in text or text.startswith("package:") or "\npackage:\n" in text
    assert "build_appimage.sh" in text
