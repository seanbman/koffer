# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Koffer onedir bundle (AppImage staging input)."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# SPECPATH is the directory containing this .spec file (packaging/).
ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"

# Ensure src layout is importable during analysis.
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

datas: list = []
binaries: list = []
hiddenimports: list = []

for pkg in ("PySide6",):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

datas += collect_data_files("koffer")
# Explicit package data that hatch force-includes for wheels.
for rel in (
    "koffer/persistence/migrations",
    "koffer/analysis/models",
    "koffer/analysis/label_maps",
):
    src_dir = SRC / rel
    if src_dir.is_dir():
        datas.append((str(src_dir), rel.replace("koffer/", "koffer/", 1)))

a = Analysis(
    [str(SRC / "koffer" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports
    + [
        "koffer",
        "koffer.app",
        "koffer.__main__",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="koffer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="koffer",
)
